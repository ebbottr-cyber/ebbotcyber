# Taiwan TWSE / TPEx network smoke: access vs feed drift

The institutional-flow provider includes two **independent** types of tests:

- **Blocking PR backend gate:** runs `pytest -q -m "not network"` (the same selector as `scripts/ci_gate.sh`). These deterministic tests check parser contracts, recorded fixtures, HTTP access/error handling and the CI gating itself. They **never require** live TPEx/TWSE connectivity and do not assert that the upstream feed was reachable.
- **Explicit opt-in live diagnostic:** run `python -m pytest -q -rs -m network tests/test_tw_institutional_network.py` in a network-connected environment. This contacts real public upstream data sources and prints the reason when a probe cannot inspect the feed. No secrets, production database changes, orders or LLM calls are involved.

The real-provider result must never be labeled successful solely because a test was skipped.

| HTTP/provider outcome | Opt-in network smoke | What it proves |
| --- | --- | --- |
| 200 with valid JSON and matching schema | Pass | Current response matches its parser contract |
| 200 with HTML or invalid JSON | Fail | An accessible endpoint returned a non-JSON payload; investigate provider drift or maintenance |
| 200 with changed columns | Fail | Actual data contract changed |
| 401/403 | Skip with exact HTTP code | Upstream access denied; schema **unverified**, not healthy |
| 408/429, or 5xx | Skip with exact HTTP code | Timeout, rate limiting or transient server outage; schema unverified |
| Transport exception | Skip with exception type | Provider cannot be reached |
| 404/410 or other unexpected status | Fail | Endpoint may be missing, migrated or unexpectedly redirecting |

The previous PR #12 CI run #43727162575 had 8,781 passing Python tests and one failure: TPEx OpenAPI returned HTTP 403 HTML to a GitHub runner. This was an **access denial**, not proof of changed TPEx JSON columns. The PR backend gate had incorrectly used bare `pytest -q` rather than the documented deterministic-only selector.

Do not work around a 403 with unauthorized credentials, proxy rotation or rate-limit evasion. Verify access from a properly permitted network when needed, and keep real-provider health and data/analysis readiness distinct.
