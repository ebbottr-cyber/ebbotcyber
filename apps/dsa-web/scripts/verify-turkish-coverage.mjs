import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const sourcePath = fileURLToPath(new URL('../src/i18n/uiText.ts', import.meta.url));
const source = readFileSync(sourcePath, 'utf8');

function section(start, end) {
  const from = source.indexOf(start);
  const to = source.indexOf(end, from + start.length);
  if (from < 0 || to < 0) throw new Error('i18n source blocks were not found');
  return source.slice(from, to);
}

function entries(block) {
  const result = new Map();
  const duplicates = [];
  for (const match of block.matchAll(/^\s*'([^']+)':\s*(.+),\s*$/gm)) {
    if (result.has(match[1])) duplicates.push(match[1]);
    result.set(match[1], match[2]);
  }
  return { result, duplicates };
}

const en = entries(section('const en:', 'const tr:'));
const tr = entries(section('const tr:', '\nexport const UI_TEXT'));
const vars = (value) => [...value.matchAll(/\{([a-zA-Z0-9_]+)\}/g)].map(x => x[1]).sort().join(',');
const errors = [
  ...en.duplicates.map(key => `Duplicate English key: ${key}`),
  ...tr.duplicates.map(key => `Duplicate Turkish key: ${key}`),
];
for (const [key, enValue] of en.result) {
  if (!tr.result.has(key)) {
    errors.push(`Turkish translation missing: ${key}`);
  } else if (vars(enValue) !== vars(tr.result.get(key))) {
    errors.push(`Placeholder mismatch: ${key} (EN: ${vars(enValue)} / TR: ${vars(tr.result.get(key))})`);
  }
}
for (const key of tr.result.keys()) {
  if (!en.result.has(key)) errors.push(`Unknown Turkish key: ${key}`);
}

const unexpectedCjk = [...tr.result].filter(([key, value]) =>
  key !== 'language.short.zh' && /[\u3400-\u9fff]/u.test(value),
);
for (const [key] of unexpectedCjk) errors.push(`Chinese characters in Turkish UI string: ${key}`);

if (errors.length) {
  console.error(errors.join('\n'));
  process.exitCode = 1;
} else {
  console.log(`All ${en.result.size} Turkish keys explicitly translated; placeholders and duplicates checked.`);
}
