import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('../src/pages/PortfolioPage.tsx', import.meta.url), 'utf8');
const start = source.indexOf('const PortfolioPage: React.FC');
assert.ok(start > 0, 'PortfolioPage component must exist');
const component = source.slice(start);

test('production portfolio literals with Chinese characters must be explicitly gated', () => {
  const violations = component.split(/\r?\n/).flatMap((line, index) =>
    /[\u3400-\u9fff]/.test(line) && !line.includes('operatorText(')
      ? [`component line ${index + 1}: ${line.trim()}`]
      : [],
  );
  assert.deepEqual(violations, [], violations.join('\n'));
});

test('production Turkish gating must not change market or broker API values', () => {
  assert.match(source, /shouldForceTurkishUi\(\) \? turkish : legacyChinese/);
  for (const code of ['"cn"', '"hk"', '"us"', '"jp"', '"kr"', '"tw"']) {
    // Identifiers may be represented with JSX double quotes; keep them intact.
    assert.ok(component.includes(code), `Missing unchanged market value ${code}`);
  }
});
