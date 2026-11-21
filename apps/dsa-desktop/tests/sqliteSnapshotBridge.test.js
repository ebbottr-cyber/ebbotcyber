'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { createHash } = require('node:crypto');
const {
  FROZEN_SNAPSHOT_COMMAND,
  createFrozenSnapshotCandidate,
  stageSnapshotRestoreCandidate,
} = require('../sqliteSnapshotBridge');

function setup(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ebbot-sqlite-electron-bridge-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const backendExe = path.join(root, 'stock_analysis.exe');
  const sourceDatabase = path.join(root, 'stock_analysis.db');
  const outputDir = path.join(root, 'snapshot');
  const restoreDir = path.join(root, 'restore');
  fs.mkdirSync(outputDir);
  fs.mkdirSync(restoreDir);
  fs.writeFileSync(backendExe, 'synthetic executable stand-in, never run');
  fs.writeFileSync(sourceDatabase, 'synthetic source database, never changed');
  return {
    backendExe,
    sourceDatabase,
    destination: path.join(outputDir, 'stock_analysis.db'),
    restoreTarget: path.join(restoreDir, 'stock_analysis.db'),
  };
}

function evidence(data) {
  return {
    status: 'PASSED',
    method: 'sqlite3.Connection.backup',
    integrity_check: 'ok',
    sha256: createHash('sha256').update(data).digest('hex'),
    size_bytes: data.length,
    release_status: 'BLOCKED',
    starts_backend: false,
    enables_updates: false,
  };
}

test('offline bridge calls only the frozen SQLite CLI and rejects secret env inheritance', (t) => {
  const ctx = setup(t);
  const bytes = Buffer.from('isolated synthetic snapshot');
  let calls = 0;
  const meta = createFrozenSnapshotCandidate({
    ...ctx,
    environment: {
      PATH: 'mock-bin',
      SystemRoot: 'C:\\Windows',
      BROKER_API_KEY: 'never-pass',
      OPENAI_API_KEY: 'never-pass',
      GH_TOKEN: 'never-pass',
      SCHEDULE_ENABLED: 'true',
    },
    runner: (file, args, options) => {
      calls += 1;
      assert.equal(file, ctx.backendExe);
      assert.deepEqual(args, [
        FROZEN_SNAPSHOT_COMMAND, '--source', ctx.sourceDatabase,
        '--destination', ctx.destination,
      ]);
      assert.equal(options.shell, false);
      assert.equal(options.windowsHide, true);
      assert.equal(options.env.OPENAI_API_KEY, undefined);
      assert.equal(options.env.BROKER_API_KEY, undefined);
      assert.equal(options.env.GH_TOKEN, undefined);
      assert.equal(options.env.SCHEDULE_ENABLED, 'false');
      fs.writeFileSync(ctx.destination, bytes);
      return { status: 0, stdout: JSON.stringify(evidence(bytes)), signal: null };
    },
  });
  assert.equal(calls, 1);
  assert.equal(meta.sha256, evidence(bytes).sha256);
  assert.equal(meta.releaseStatus, 'BLOCKED');
  assert.equal(fs.readFileSync(ctx.sourceDatabase, 'utf8'), 'synthetic source database, never changed');
});

test('restore candidate is staged in new location without touching existing files', (t) => {
  const ctx = setup(t);
  const bytes = Buffer.from('offline synthetic one-file SQLite snapshot');
  fs.writeFileSync(ctx.destination, bytes);
  const result = stageSnapshotRestoreCandidate({
    snapshotFile: ctx.destination,
    destination: ctx.restoreTarget,
    expectedSha256: evidence(bytes).sha256,
    expectedSize: bytes.length,
  });
  assert.equal(result.status, 'STAGED_ONLY');
  assert.equal(result.installationAllowed, false);
  assert.equal(result.releaseStatus, 'BLOCKED');
  assert.deepEqual(fs.readFileSync(ctx.restoreTarget), bytes);
  assert.deepEqual(fs.readFileSync(ctx.destination), bytes);
  assert.equal(fs.existsSync(ctx.restoreTarget + '-wal'), false);
  assert.equal(fs.existsSync(ctx.restoreTarget + '-shm'), false);
  assert.deepEqual(fs.readdirSync(path.dirname(ctx.restoreTarget)), ['stock_analysis.db']);
});

test('existing database and stale WAL or SHM sidecars refuse staged restore', (t) => {
  const ctx = setup(t);
  const bytes = Buffer.from('trusted candidate');
  fs.writeFileSync(ctx.destination, bytes);
  const args = {
    snapshotFile: ctx.destination,
    destination: ctx.restoreTarget,
    expectedSha256: evidence(bytes).sha256,
    expectedSize: bytes.length,
  };
  fs.writeFileSync(ctx.restoreTarget, 'valuable existing data');
  assert.throws(() => stageSnapshotRestoreCandidate(args), /must not exist/);
  assert.equal(fs.readFileSync(ctx.restoreTarget, 'utf8'), 'valuable existing data');
  fs.rmSync(ctx.restoreTarget);
  fs.writeFileSync(ctx.restoreTarget + '-wal', 'uncheckpointed transactions');
  assert.throws(() => stageSnapshotRestoreCandidate(args), /WAL\/SHM/);
  assert.equal(fs.readFileSync(ctx.restoreTarget + '-wal', 'utf8'), 'uncheckpointed transactions');
  fs.rmSync(ctx.restoreTarget + '-wal');
  fs.writeFileSync(ctx.restoreTarget + '-shm', 'shared memory sidecar');
  assert.throws(() => stageSnapshotRestoreCandidate(args), /WAL\/SHM/);
  assert.equal(fs.existsSync(ctx.restoreTarget), false);
});

test('altered snapshot, wrong digest and malformed frozen output cannot pass', (t) => {
  const ctx = setup(t);
  const bytes = Buffer.from('trusted candidate');
  fs.writeFileSync(ctx.destination, bytes);
  const meta = evidence(bytes);
  assert.throws(() => stageSnapshotRestoreCandidate({
    snapshotFile: ctx.destination, destination: ctx.restoreTarget,
    expectedSha256: '0'.repeat(64), expectedSize: bytes.length,
  }), /SHA-256/);
  assert.equal(fs.existsSync(ctx.restoreTarget), false);
  assert.throws(() => createFrozenSnapshotCandidate({
    ...ctx, destination: path.join(path.dirname(ctx.destination), 'invalid.db'),
    runner: () => ({ status: 0, stdout: '{bad json', signal: null }),
  }), /invalid JSON/);
  fs.rmSync(ctx.destination);
  assert.throws(() => createFrozenSnapshotCandidate({
    ...ctx,
    runner: (_exe, _args) => {
      fs.writeFileSync(ctx.destination, bytes);
      return { status: 0, stdout: JSON.stringify({ ...meta, release_status: 'READY' }) };
    },
  }), /incomplete or not fail-closed/);
});

test('staging publication failure leaves no final output or temporary candidate', (t) => {
  const ctx = setup(t);
  const bytes = Buffer.from('valid synthetic snapshot');
  fs.writeFileSync(ctx.destination, bytes);
  const originalLink = fs.linkSync;
  fs.linkSync = () => { throw new Error('Windows hardlink refused'); };
  t.after(() => { fs.linkSync = originalLink; });
  assert.throws(() => stageSnapshotRestoreCandidate({
    snapshotFile: ctx.destination,
    destination: ctx.restoreTarget,
    expectedSha256: evidence(bytes).sha256,
    expectedSize: bytes.length,
  }), /hardlink refused/);
  assert.equal(fs.existsSync(ctx.restoreTarget), false);
  assert.deepEqual(fs.readdirSync(path.dirname(ctx.restoreTarget)), []);
  assert.deepEqual(fs.readFileSync(ctx.destination), bytes);
});

test('symbolic-link snapshot input cannot be staged', (t) => {
  const ctx = setup(t);
  const bytes = Buffer.from('valid candidate');
  fs.writeFileSync(ctx.destination, bytes);
  const linked = path.join(path.dirname(ctx.destination), 'link.db');
  try {
    fs.symlinkSync(ctx.destination, linked);
  } catch (_error) {
    t.skip('Windows runner does not grant symbolic-link creation');
    return;
  }
  assert.throws(() => stageSnapshotRestoreCandidate({
    snapshotFile: linked,
    destination: ctx.restoreTarget,
    expectedSha256: evidence(bytes).sha256,
    expectedSize: bytes.length,
  }), /non-symlink/);
  assert.equal(fs.existsSync(ctx.restoreTarget), false);
});
