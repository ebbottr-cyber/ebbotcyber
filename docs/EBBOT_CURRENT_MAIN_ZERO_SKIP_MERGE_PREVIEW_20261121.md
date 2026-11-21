# EBBot exact Git merge preview — current main versus zero-skipped React

This is a **read-only, pinned SHA, Git merge-tree** evidence gate, not an automated merge.

- main: `b31c8195bd9650af8c3faa5e3f88fd576c14ab21` (adds safe Windows packaged React usage-period and AI filter controls).
- PR #182 zero-skipped React candidate: `a7571ca13ed8cc896e67bb0935c5f804c0ac751f`; [GitHub Actions 44888252707](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44888252707) gave 1,528 PASS, zero skipped.
- Real `git merge-tree --write-tree --messages` calculates overlap and content conflicts and uploads JSON; unexpected main/candidate branch movement makes the run fail closed.
- No merge, no installer run, no API key, no scheduler, no paper/live trading, no updater or release.
- **Even conflict-free Git preview is not proof of behavior**, requires independent Windows, backend, React and security review; `main.protected=false`.
