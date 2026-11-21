'use strict';

// Offline bridge only: intentionally NOT called by the desktop update or
// startup path. No installed application or existing SQLite database is altered.
const fs = require('node:fs');
const path = require('node:path');
const { createHash, randomBytes } = require('node:crypto');
const { spawnSync } = require('node:child_process');

const FROZEN_SNAPSHOT_COMMAND = '--ebbot-desktop-sqlite-snapshot';

function requireRegularFile(file, label) {
  if (typeof file !== 'string' || !path.isAbsolute(file)) {
    throw new Error(`${label} must be an absolute path`);
  }
  const stat = fs.lstatSync(file);
  if (stat.isSymbolicLink() || !stat.isFile()) {
    throw new Error(`${label} must be a regular non-symlink file`);
  }
  return stat;
}

function requireUnusedDestination(destination, label) {
  if (typeof destination !== 'string' || !path.isAbsolute(destination)) {
    throw new Error(`${label} must be an absolute path`);
  }
  const parent = path.dirname(destination);
  const parentStat = fs.lstatSync(parent);
  if (parentStat.isSymbolicLink() || !parentStat.isDirectory()) {
    throw new Error(`${label} parent must be a regular directory`);
  }
  // lstatSync recognizes dangling symlinks, unlike existsSync().
  if (fs.existsSync(destination) || fs.lstatSync(destination, { throwIfNoEntry: false })) {
    throw new Error(`${label} must not exist or overwrite previous user data`);
  }
  // existsSync() follows the final symlink and reports false for a dangling
  // WAL/SHM link. lstatSync() must reject *any* filesystem entry, including
  // broken links, before a snapshot/staged restore is allowed to proceed.
  for (const sidecar of [destination + '-wal', destination + '-shm']) {
    if (fs.lstatSync(sidecar, { throwIfNoEntry: false })) {
      throw new Error(`${label} has existing SQLite WAL/SHM sidecar files`);
    }
  }
}

function sha256File(filename) {
  const hash = createHash('sha256');
  const file = fs.openSync(filename, 'r');
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  try {
    while (true) {
      const count = fs.readSync(file, buffer, 0, buffer.length, null);
      if (!count) break;
      hash.update(buffer.subarray(0, count));
    }
  } finally {
    fs.closeSync(file);
  }
  return hash.digest('hex');
}

function validateSnapshotReport(report, snapshotFile) {
  if (!report || typeof report !== 'object' ||
      report.status !== 'PASSED' ||
      report.method !== 'sqlite3.Connection.backup' ||
      report.integrity_check !== 'ok' ||
      report.release_status !== 'BLOCKED' ||
      report.starts_backend !== false ||
      report.enables_updates !== false ||
      typeof report.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(report.sha256) ||
      !Number.isSafeInteger(report.size_bytes) || report.size_bytes <= 0) {
    throw new Error('Frozen SQLite snapshot evidence is incomplete or not fail-closed');
  }
  const size = requireRegularFile(snapshotFile, 'Snapshot').size;
  if (size !== report.size_bytes || sha256File(snapshotFile) !== report.sha256) {
    throw new Error('Frozen SQLite snapshot SHA-256 or file size mismatch');
  }
  return Object.freeze({
    method: 'sqlite3.Connection.backup',
    sha256: report.sha256,
    sizeBytes: size,
    releaseStatus: 'BLOCKED',
  });
}

function restrictedChildEnvironment(current = process.env) {
  // No API keys, broker tokens, or third-party credentials inherited by the
  // one-shot SQLite tool, which exits before EBBot config is bootstrapped.
  const allowed = ['SystemRoot', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP',
    'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'PROGRAMDATA', 'HOME'];
  const out = {};
  for (const name of allowed) {
    if (typeof current[name] === 'string') out[name] = current[name];
  }
  out.MEME_COIN_DISCOVERY_ENABLED = 'false';
  out.SCHEDULE_ENABLED = 'false';
  out.RUNTIME_SCHEDULER_FORCE_ENABLED = 'false';
  return out;
}

function createFrozenSnapshotCandidate({
  backendExe, sourceDatabase, destination, runner = spawnSync, environment = process.env,
}) {
  requireRegularFile(backendExe, 'Frozen backend');
  if (path.basename(backendExe).toLowerCase() !== 'stock_analysis.exe') {
    throw new Error('Only the EBBot packaged backend is allowed for this offline bridge');
  }
  requireRegularFile(sourceDatabase, 'Source SQLite database');
  requireUnusedDestination(destination, 'Snapshot destination');
  if (path.resolve(sourceDatabase) === path.resolve(destination)) {
    throw new Error('Snapshot destination cannot be the source database');
  }
  const result = runner(
    backendExe,
    [FROZEN_SNAPSHOT_COMMAND, '--source', sourceDatabase, '--destination', destination],
    {
      shell: false,
      windowsHide: true,
      encoding: 'utf8',
      timeout: 60000,
      maxBuffer: 8192,
      env: restrictedChildEnvironment(environment),
    },
  );
  if (!result || result.error || result.status !== 0 || result.signal) {
    throw new Error('Frozen offline SQLite snapshot command failed');
  }
  let report;
  try {
    report = JSON.parse(result.stdout);
  } catch (_error) {
    throw new Error('Frozen SQLite snapshot returned invalid JSON');
  }
  return validateSnapshotReport(report, destination);
}

function stageSnapshotRestoreCandidate({ snapshotFile, destination, expectedSha256, expectedSize }) {
  requireRegularFile(snapshotFile, 'Snapshot');
  requireUnusedDestination(destination, 'Staged restore target');
  // Only an empty, new offline staging location is supported. We intentionally
  // do not replace an installed database or its WAL/SHM files.
  if (path.resolve(snapshotFile) === path.resolve(destination)) {
    throw new Error('Restore target cannot be the source snapshot');
  }
  const evidence = validateSnapshotReport({
    status: 'PASSED', method: 'sqlite3.Connection.backup',
    integrity_check: 'ok', release_status: 'BLOCKED',
    starts_backend: false, enables_updates: false,
    sha256: expectedSha256, size_bytes: expectedSize,
  }, snapshotFile);
  const temporary = path.join(
    path.dirname(destination),
    `.ebbot-restore-candidate-${randomBytes(12).toString('hex')}`,
  );
  try {
    fs.copyFileSync(snapshotFile, temporary, fs.constants.COPYFILE_EXCL);
    if (sha256File(temporary) !== evidence.sha256 ||
        fs.statSync(temporary).size !== evidence.sizeBytes) {
      throw new Error('Staged restore copy did not match the approved SHA-256');
    }
    // Same-directory hard-link publication is atomic and fails if the
    // destination was created by somebody else after our preflight.
    fs.linkSync(temporary, destination);
  } finally {
    try { fs.unlinkSync(temporary); } catch (_ignored) {}
  }
  return Object.freeze({ ...evidence, status: 'STAGED_ONLY', installationAllowed: false });
}

module.exports = {
  FROZEN_SNAPSHOT_COMMAND,
  createFrozenSnapshotCandidate,
  restrictedChildEnvironment,
  sha256File,
  stageSnapshotRestoreCandidate,
  validateSnapshotReport,
};
