'use strict';

// ISOLATED REHEARSAL ONLY. This module never accesses EBBot's installed
// database, automatic update path or real user files. All input is bounded
// synthetic Buffer data; the workspace is freshly created under os.tmpdir().
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const MARKER = 'EBBOT_SQLITE_BUNDLE_REHEARSAL_ONLY_V1';
const DB = 'stock_analysis.db';
const SIDECARS = [DB + '-wal', DB + '-shm'];
const LIMIT = 64 * 1024;

function validateBytes(bytes, name, required) {
  if (bytes === undefined && !required) return;
  if (!Buffer.isBuffer(bytes) || bytes.length === 0 || bytes.length > LIMIT) {
    throw new Error(`${name} must be a bounded non-empty synthetic Buffer`);
  }
}

function assertWorkspace(root) {
  if (typeof root !== 'string' || !path.isAbsolute(root) ||
      !path.basename(root).startsWith('ebbot-sqlite-rehearsal-')) {
    throw new Error('Only isolated SQLite rehearsal workspaces are accepted');
  }
  const tempRoot = fs.realpathSync(os.tmpdir());
  const resolvedRoot = fs.realpathSync(root);
  if (fs.lstatSync(root).isSymbolicLink() ||
      path.dirname(resolvedRoot).toLowerCase() !== tempRoot.toLowerCase()) {
    throw new Error('Recovery workspace must be a direct non-symlink child of the temp directory');
  }
  if (fs.readFileSync(path.join(root, '.offline-rehearsal-marker'), 'utf8') !== MARKER) {
    throw new Error('Offline rehearsal marker missing or invalid');
  }
  return root;
}

function isPresent(p) {
  return fs.existsSync(p) || fs.lstatSync(p, { throwIfNoEntry: false }) !== undefined;
}

function assertDataDirectory(directory, allowed) {
  const stat = fs.lstatSync(directory);
  if (stat.isSymbolicLink() || !stat.isDirectory()) {
    throw new Error('SQLite rehearsal bundle is not a regular directory');
  }
  const files = fs.readdirSync(directory).sort();
  if (!files.includes(DB) || files.some((name) => !allowed.includes(name))) {
    throw new Error('SQLite bundle contains missing or unapproved files');
  }
  for (const name of files) {
    const entry = fs.lstatSync(path.join(directory, name));
    if (entry.isSymbolicLink() || !entry.isFile()) {
      throw new Error('SQLite bundle contains a link or non-regular file');
    }
  }
  return files;
}

function createSqliteBundleRehearsal({ existingDb, existingWal, existingShm, candidateDb }) {
  validateBytes(existingDb, 'Original DB', true);
  validateBytes(existingWal, 'Original WAL', false);
  validateBytes(existingShm, 'Original SHM', false);
  validateBytes(candidateDb, 'Candidate snapshot', true);
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ebbot-sqlite-rehearsal-'));
  try {
    fs.writeFileSync(path.join(root, '.offline-rehearsal-marker'), MARKER, { flag: 'wx' });
    for (const name of ['active', 'candidate']) fs.mkdirSync(path.join(root, name));
    fs.writeFileSync(path.join(root, 'active', DB), existingDb, { flag: 'wx' });
    if (existingWal) fs.writeFileSync(path.join(root, 'active', SIDECARS[0]), existingWal, { flag: 'wx' });
    if (existingShm) fs.writeFileSync(path.join(root, 'active', SIDECARS[1]), existingShm, { flag: 'wx' });
    fs.writeFileSync(path.join(root, 'candidate', DB), candidateDb, { flag: 'wx' });
    return root;
  } catch (error) {
    fs.rmSync(root, { recursive: true, force: true });
    throw error;
  }
}

function rehearseSqlitePromotion(root, { afterSavingOld = null } = {}) {
  assertWorkspace(root);
  const active = path.join(root, 'active');
  const candidate = path.join(root, 'candidate');
  const previous = path.join(root, 'previous');
  if (isPresent(previous) || isPresent(path.join(root, 'candidate-quarantine'))) {
    throw new Error('Previous rollback evidence exists; promotion refused');
  }
  assertDataDirectory(active, [DB, ...SIDECARS]);
  assertDataDirectory(candidate, [DB]); // No candidate WAL/SHM may mix with the old DB.
  fs.renameSync(active, previous);
  try {
    if (afterSavingOld) afterSavingOld();
    fs.renameSync(candidate, active);
  } catch (error) {
    // If a simulated interruption occurs after the first rename, do not
    // leave the original data unavailable when a rollback remains possible.
    if (!isPresent(active) && isPresent(previous)) {
      try { fs.renameSync(previous, active); } catch (_recoverLater) {
        // Keep previous intact for explicit recovery; never delete the trio.
      }
    }
    throw error;
  }
  return {
    status: 'CANDIDATE_ACTIVE_PREVIOUS_RETAINED',
    releaseStatus: 'BLOCKED',
    installAllowed: false,
    rollbackAvailable: true,
  };
}

function recoverInterruptedSqlitePromotion(root) {
  assertWorkspace(root);
  const active = path.join(root, 'active');
  const previous = path.join(root, 'previous');
  if (isPresent(previous) && !isPresent(active)) {
    assertDataDirectory(previous, [DB, ...SIDECARS]);
    fs.renameSync(previous, active);
    return { status: 'ORIGINAL_RECOVERED', releaseStatus: 'BLOCKED' };
  }
  if (isPresent(previous) && isPresent(active)) {
    assertDataDirectory(previous, [DB, ...SIDECARS]);
    assertDataDirectory(active, [DB]);
    return { status: 'REVIEW_REQUIRED', releaseStatus: 'BLOCKED' };
  }
  if (isPresent(active)) {
    assertDataDirectory(active, [DB, ...SIDECARS]);
    return { status: 'NO_PENDING_SWAP', releaseStatus: 'BLOCKED' };
  }
  throw new Error('Missing original database and recovery bundle');
}

function rollbackCompletedSqlitePromotion(root) {
  assertWorkspace(root);
  const active = path.join(root, 'active');
  const previous = path.join(root, 'previous');
  const quarantine = path.join(root, 'candidate-quarantine');
  if (!isPresent(active) || !isPresent(previous) || isPresent(quarantine)) {
    throw new Error('Rollback requires both active candidate and original recovery bundle');
  }
  assertDataDirectory(active, [DB]);
  assertDataDirectory(previous, [DB, ...SIDECARS]);
  fs.renameSync(active, quarantine);
  try {
    fs.renameSync(previous, active);
  } catch (error) {
    // Preserve the original in previous and the new copy in quarantine.
    // RecoverInterruptedSqlitePromotion can retry the original rename.
    throw error;
  }
  return { status: 'ORIGINAL_RESTORED_CANDIDATE_QUARANTINED',
    releaseStatus: 'BLOCKED', installAllowed: false };
}

module.exports = {
  createSqliteBundleRehearsal,
  rehearseSqlitePromotion,
  recoverInterruptedSqlitePromotion,
  rollbackCompletedSqlitePromotion,
};
