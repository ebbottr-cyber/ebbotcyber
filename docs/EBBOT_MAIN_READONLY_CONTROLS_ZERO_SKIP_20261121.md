# EBBot latest main read-only React controls plus 1,528-test zero-skip candidate

Strictly a DRAFT. Inputs: PR182 a7571ca13ed8cc896e67bb0935c5f804c0ac751f, main b31c8195bd9650af8c3faa5e3f88fd576c14ab21 (21 November 2026).

Preserved: 2 previously skipped Shell interactions, 1,528 React testcases, desktop SQLite WAL atomic snapshot/restore/rollback protections, NSIS --publish never, restricted frozen health probe, updater disabled.

Added latest-main CI-only Windows evidence: GET/HEAD-only Electron request filter (deny POST/PUT/DELETE even on localhost); React Usage period toggle and AI Signals filters with real state transitions and zero submit; safe data-testid and aria-pressed selectors; Turkish date locale; 13 screening translation keys in each zh/en/tr, retaining candidate comprehensive L() translation on the other screening sections. Existing nav labels Piyasa Özeti and Hisse Analizi are verified instead of obsolete Ana Sayfa.

All CI assertions must use the exact final merged head SHA. The main branch still lacks protection, and independent code signing/SmartScreen, real-device upgrade and user SQLite migration are outstanding. No release, no main merge, no install, no orders, no scheduler.