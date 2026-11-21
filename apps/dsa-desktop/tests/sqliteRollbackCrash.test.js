'use strict';

// Each test ends a separate Node process in the middle of an actual filesystem
// rename. It uses ONLY random, bounded, synthetic data inside os.tmpdir().
// No Electron application, backend process, real DB or installer is launched.
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const {
  createSqliteBundleRehearsal,
  rehearseSqlitePromotion,
  recoverInterruptedSqlitePromotion,
  rollbackCompletedSqlitePromotion,
} = require('../sqliteRollbackRehearsal');

const DB = 'stock_analysis.db';
const ORIGINAL = Buffer.from('crash-test-old-synthetic-sqlite');
const WAL = Buffer.from('crash-test-old-synthetic-WAL');
const SHM = Buffer.from('crash-test-old-synthetic-SHM');
const NEW = Buffer.from('crash-test-new-synthetic-snapshot');
const modulePath = require.resolve('../sqliteRollbackRehearsal');

// No cleanup handler runs in this child after process.exit(). Unlike throwing
// an exception, it does not run catch/finally in the rehearsal helper.
const abruptChildCode = `
const fs = require('node:fs');
const path = require('node:path');
const root = process.argv[1];
const helper = require(process.argv[2]);
const mode = process.argv[3];
const oldRename = fs.renameSync;
fs.renameSync = (from, to) => {
  const result = oldRename(from, to);
  if (mode === 'after-old-save' &&
      from === path.join(root, 'active') && to === path.join(root, 'previous')) {
    process.exit(71);
  }
  if (mode === 'after-new-promote' &&
      from === path.join(root, 'candidate') && to === path.join(root, 'active')) {
    process.exit(72);
  }
  if (mode === 'during-rollback' &&
      from === path.join(root, 'active') &&
      to === path.join(root, 'candidate-quarantine')) {
    process.exit(73);
  }
  return result;
};
if (mode === 'during-rollback') helper.rollbackCompletedSqlitePromotion(root);
else helper.rehearseSqlitePromotion(root);
process.exit(0);
`;

function create(t) {
  const root = createSqliteBundleRehearsal({
    existingDb: ORIGINAL,
    existingWal: WAL,
    existingShm: SHM,
    candidateDb: NEW,
  });
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

function assertTrio(root, dir = 'active') {
  const folder = path.join(root, dir);
  assert.deepEqual(fs.readFileSync(path.join(folder, DB)), ORIGINAL);
  assert.deepEqual(fs.readFileSync(path.join(folder, DB + '-wal')), WAL);
  assert.deepEqual(fs.readFileSync(path.join(folder, DB + '-shm')), SHM);
}

function abruptExit(root, mode, code) {
  const child = spawnSync(process.execPath,
    ['-e', abruptChildCode, root, modulePath, mode],
    { shell: false, timeout: 15000, windowsHide: true, encoding: 'utf8', maxBuffer: 4096 });
  assert.equal(child.error, undefined, child.error?.message);
  assert.equal(child.signal, null, `Child terminated by unexpected signal: ${child.signal}`);
  assert.equal(child.status, code,
    `Unexpected crash-checkpoint status=${child.status}, stderr=${String(child.stderr).slice(0, 350)}`);
}

test('abrupt independent process exit after saving original retains DB WAL SHM for restart', (t) => {
  const root = create(t);
  abruptExit(root, 'after-old-save', 71);
  assert.equal(fs.existsSync(path.join(root, 'active')), false);
  assertTrio(root, 'previous');
  assert.deepEqual(fs.readFileSync(path.join(root, 'candidate', DB)), NEW);

  const recovered = recoverInterruptedSqlitePromotion(root);
  assert.equal(recovered.status, 'ORIGINAL_RECOVERED');
  assert.equal(recovered.releaseStatus, 'BLOCKED');
  assertTrio(root);
  assert.deepEqual(fs.readFileSync(path.join(root, 'candidate', DB)), NEW);
});

test('abrupt independent process exit after candidate activation requires explicit review', (t) => {
  const root = create(t);
  abruptExit(root, 'after-new-promote', 72);
  assertTrio(root, 'previous');
  assert.deepEqual(fs.readFileSync(path.join(root, 'active', DB)), NEW);
  assert.deepEqual(fs.readdirSync(path.join(root, 'active')), [DB]);

  const review = recoverInterruptedSqlitePromotion(root);
  assert.equal(review.status, 'REVIEW_REQUIRED');
  assert.equal(review.releaseStatus, 'BLOCKED');
  assertTrio(root, 'previous');

  const rollback = rollbackCompletedSqlitePromotion(root);
  assert.equal(rollback.status, 'ORIGINAL_RESTORED_CANDIDATE_QUARANTINED');
  assertTrio(root);
  assert.deepEqual(fs.readFileSync(path.join(root, 'candidate-quarantine', DB)), NEW);
});

test('abrupt independent process exit mid-rollback keeps both generations and recovers original', (t) => {
  const root = create(t);
  rehearseSqlitePromotion(root);
  abruptExit(root, 'during-rollback', 73);
  assert.equal(fs.existsSync(path.join(root, 'active')), false);
  assertTrio(root, 'previous');
  assert.deepEqual(fs.readFileSync(path.join(root, 'candidate-quarantine', DB)), NEW);

  const recovery = recoverInterruptedSqlitePromotion(root);
  assert.equal(recovery.status, 'ORIGINAL_RECOVERED');
  assertTrio(root);
  assert.deepEqual(fs.readFileSync(path.join(root, 'candidate-quarantine', DB)), NEW);
  assert.equal(recoverInterruptedSqlitePromotion(root).status, 'NO_PENDING_SWAP');
});
