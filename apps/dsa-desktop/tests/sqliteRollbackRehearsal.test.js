'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {
  createSqliteBundleRehearsal,
  rehearseSqlitePromotion,
  recoverInterruptedSqlitePromotion,
  rollbackCompletedSqlitePromotion,
} = require('../sqliteRollbackRehearsal');

const fixture = {
  existingDb: Buffer.from('original-synthetic-db'),
  existingWal: Buffer.from('original-uncheckpointed-WAL'),
  existingShm: Buffer.from('original-shared-memory-SHM'),
  candidateDb: Buffer.from('new-single-file-snapshot'),
};
const db = 'stock_analysis.db';

function make(t) {
  const root = createSqliteBundleRehearsal(fixture);
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

function bytes(root, bundle, basename = db) {
  return fs.readFileSync(path.join(root, bundle, basename));
}

function assertOriginal(root, directory = 'active') {
  assert.deepEqual(bytes(root, directory), fixture.existingDb);
  assert.deepEqual(bytes(root, directory, db + '-wal'), fixture.existingWal);
  assert.deepEqual(bytes(root, directory, db + '-shm'), fixture.existingShm);
}

test('successful isolated swap keeps the full old DB/WAL/SHM for explicit rollback', (t) => {
  const root = make(t);
  const outcome = rehearseSqlitePromotion(root);
  assert.equal(outcome.releaseStatus, 'BLOCKED');
  assert.equal(outcome.installAllowed, false);
  assert.equal(outcome.rollbackAvailable, true);
  assert.deepEqual(bytes(root, 'active'), fixture.candidateDb);
  assert.deepEqual(fs.readdirSync(path.join(root, 'active')), [db]);
  assertOriginal(root, 'previous');
  assert.equal(recoverInterruptedSqlitePromotion(root).status, 'REVIEW_REQUIRED');
  assertOriginal(root, 'previous');
});

test('explicit rollback restores old DB/WAL/SHM and quarantines new candidate', (t) => {
  const root = make(t);
  rehearseSqlitePromotion(root);
  const outcome = rollbackCompletedSqlitePromotion(root);
  assert.equal(outcome.status, 'ORIGINAL_RESTORED_CANDIDATE_QUARANTINED');
  assertOriginal(root);
  assert.deepEqual(bytes(root, 'candidate-quarantine'), fixture.candidateDb);
  assert.equal(fs.existsSync(path.join(root, 'previous')), false);
  assert.throws(() => rehearseSqlitePromotion(root), /rollback evidence exists/);
});

test('interrupted swap between two renames restores old trio and keeps candidate', (t) => {
  const root = make(t);
  assert.throws(() => rehearseSqlitePromotion(root, {
    afterSavingOld: () => { throw new Error('simulated power interruption'); },
  }), /simulated power interruption/);
  assertOriginal(root);
  assert.deepEqual(bytes(root, 'candidate'), fixture.candidateDb);
  assert.equal(fs.existsSync(path.join(root, 'previous')), false);
});

test('restart recovery after an abrupt crash restores old trio, not mixed snapshot', (t) => {
  const root = make(t);
  fs.renameSync(path.join(root, 'active'), path.join(root, 'previous'));
  assert.equal(fs.existsSync(path.join(root, 'active')), false);
  assert.equal(recoverInterruptedSqlitePromotion(root).status, 'ORIGINAL_RECOVERED');
  assertOriginal(root);
  assert.deepEqual(bytes(root, 'candidate'), fixture.candidateDb);
  assert.equal(recoverInterruptedSqlitePromotion(root).status, 'NO_PENDING_SWAP');
});

test('failed rollback leaves original and candidate available for manual retry', (t) => {
  const root = make(t);
  rehearseSqlitePromotion(root);
  const realRename = fs.renameSync;
  const originalPath = path.join(root, 'previous');
  const activePath = path.join(root, 'active');
  fs.renameSync = (from, to) => {
    if (from === originalPath && to === activePath) throw new Error('Windows target directory locked');
    return realRename(from, to);
  };
  try {
    assert.throws(() => rollbackCompletedSqlitePromotion(root), /directory locked/);
  } finally {
    fs.renameSync = realRename;
  }
  assert.equal(fs.existsSync(activePath), false);
  assertOriginal(root, 'previous');
  assert.deepEqual(bytes(root, 'candidate-quarantine'), fixture.candidateDb);
  assert.equal(recoverInterruptedSqlitePromotion(root).status, 'ORIGINAL_RECOVERED');
  assertOriginal(root);
  assert.deepEqual(bytes(root, 'candidate-quarantine'), fixture.candidateDb);
});

test('Windows EBUSY before first swap preserves original DB WAL and SHM', (t) => {
  const root = make(t);
  const originalRename = fs.renameSync;
  fs.renameSync = (from, to) => {
    if (from === path.join(root, 'active') && to === path.join(root, 'previous')) {
      const error = new Error('Windows SQLite directory locked');
      error.code = 'EBUSY';
      throw error;
    }
    return originalRename(from, to);
  };
  try {
    assert.throws(() => rehearseSqlitePromotion(root), /directory locked/);
  } finally {
    fs.renameSync = originalRename;
  }
  assertOriginal(root);
  assert.deepEqual(bytes(root, 'candidate'), fixture.candidateDb);
  assert.equal(fs.existsSync(path.join(root, 'previous')), false);
});

test('two blocked rename attempts retain previous DB WAL SHM for startup retry', (t) => {
  const root = make(t);
  const realRename = fs.renameSync;
  const active = path.join(root, 'active');
  const candidate = path.join(root, 'candidate');
  const previous = path.join(root, 'previous');
  fs.renameSync = (from, to) => {
    if ((from === candidate && to === active) ||
        (from === previous && to === active)) {
      const error = new Error('simulated Windows file-lock after moving old bundle');
      error.code = 'EBUSY';
      throw error;
    }
    return realRename(from, to);
  };
  try {
    assert.throws(() => rehearseSqlitePromotion(root), /file-lock/);
  } finally {
    fs.renameSync = realRename;
  }
  assert.equal(fs.existsSync(active), false);
  assertOriginal(root, 'previous');
  assert.deepEqual(bytes(root, 'candidate'), fixture.candidateDb);
  assert.equal(recoverInterruptedSqlitePromotion(root).status, 'ORIGINAL_RECOVERED');
  assertOriginal(root);
});

test('startup recovery also fails closed if Windows keeps previous bundle locked', (t) => {
  const root = make(t);
  const active = path.join(root, 'active');
  const previous = path.join(root, 'previous');
  fs.renameSync(active, previous);
  const realRename = fs.renameSync;
  fs.renameSync = (from, to) => {
    if (from === previous && to === active) {
      const error = new Error('startup retry still blocked by Windows file lock');
      error.code = 'EACCES';
      throw error;
    }
    return realRename(from, to);
  };
  try {
    assert.throws(() => recoverInterruptedSqlitePromotion(root), /still blocked/);
  } finally {
    fs.renameSync = realRename;
  }
  assert.equal(fs.existsSync(active), false);
  assertOriginal(root, 'previous');
  assert.equal(recoverInterruptedSqlitePromotion(root).status, 'ORIGINAL_RECOVERED');
  assertOriginal(root);
});

test('corrupt or unexpected WAL replacement candidate is rejected before moving old data', (t) => {
  const root = make(t);
  fs.writeFileSync(path.join(root, 'candidate', db + '-wal'), 'unapproved new WAL');
  assert.throws(() => rehearseSqlitePromotion(root), /unapproved files/);
  assertOriginal(root);
  assert.equal(fs.existsSync(path.join(root, 'previous')), false);
});

test('missing original DB or unexpected file refuses swap without cleanup', (t) => {
  const root = make(t);
  fs.rmSync(path.join(root, 'active', db));
  assert.throws(() => rehearseSqlitePromotion(root), /missing or unapproved files/);
  assert.equal(fs.existsSync(path.join(root, 'previous')), false);
  assert.deepEqual(bytes(root, 'active', db + '-wal'), fixture.existingWal);
  assert.deepEqual(bytes(root, 'active', db + '-shm'), fixture.existingShm);
});

test('symlink or unauthorized workspace cannot affect real files', (t) => {
  const root = make(t);
  const separate = fs.mkdtempSync(path.join(os.tmpdir(), 'ebbot-other-dir-'));
  t.after(() => fs.rmSync(separate, { recursive: true, force: true }));
  fs.writeFileSync(path.join(separate, 'do-not-touch.txt'), 'current-user-data');
  assert.throws(() => rehearseSqlitePromotion(separate), /Only isolated/);
  assert.equal(fs.readFileSync(path.join(separate, 'do-not-touch.txt'), 'utf8'), 'current-user-data');
  const linkedDb = path.join(root, 'candidate', db);
  fs.rmSync(linkedDb);
  try {
    fs.symlinkSync(path.join(root, 'active', db), linkedDb);
  } catch (_error) {
    t.skip('Symbolic links unavailable on this Windows runner');
    return;
  }
  assert.throws(() => rehearseSqlitePromotion(root), /link or non-regular/);
  assertOriginal(root);
});

test('invalid and oversized synthetic input cannot create a recovery workspace', () => {
  assert.throws(() => createSqliteBundleRehearsal({
    ...fixture, existingDb: 'real path instead of synthetic buffer',
  }), /synthetic Buffer/);
  assert.throws(() => createSqliteBundleRehearsal({
    ...fixture, candidateDb: Buffer.alloc(65 * 1024),
  }), /synthetic Buffer/);
});

test('a missing original and missing recovery copy fails closed rather than claim success', (t) => {
  const root = make(t);
  fs.rmSync(path.join(root, 'active'), { recursive: true, force: true });
  assert.throws(() => recoverInterruptedSqlitePromotion(root), /Missing original database/);
});
