# V1 verification — October 16, 2026

- **42 pytest tests passed**, including all **19 shared policy evaluation scenarios**. The suite covers source-backed identity candidates, field thresholds, policy-only attempts, aliases/alternate IDs, corrections, early topics, ambiguity, cross-party reads, role changes, deadline precedence, document guidance, monetary distinctions, representative scopes, consent expiry/retries/deduplication, CSRF/origin checks, encrypted persistence, model failure, durable leases, and restart recovery.
- **6 Playwright acceptance tests passed** against a separate offline server: complete denial/summary/Send/resume flow; injection/verification boundary; January ambiguity and Skip; Evaluation Lab replay/reset; mobile inspector focus restoration/no horizontal overflow; network failure/retry with bounded page layout.
- **Production frontend build passed**, including strict TypeScript checking. Main JS is approximately 107 kB gzip; CSS approximately 7 kB gzip.
- **6-call live Sol probe passed** with `gpt-6.1-sol`, prompt `claimflow-extract-v1`, fixture hash `328f5c17f69b`. Run completed at 2026-10-16 08:47 UTC. It used **6,550 total tokens**, with per-call latency **2.8–5.6 seconds**. Cases: partial identity/early document question; remaining identity and retained question; anxiety/payment distinction; wrap-up without Send; injection; unauthorized David. The sanitized reusable report is in ignored `data/live-evaluation.json` on the development machine.
- Manual in-app browser check confirmed the live guided opening, authorized claim response, inspector progression, and summary preview with explicit Send/Skip controls. A preview is saved in `docs/claimflow-preview.jpg`.
- Earlier two-call integration smoke also succeeded for Margaret's full opening and an anxious document-alternative follow-up. Key authentication and model availability were checked without exposing the key.

The browser run found and fixed a mobile dialog focus-restoration defect. Initial browser launches required permission to run Chromium outside the macOS filesystem sandbox; the suite then ran successfully. The test server's explicit allowed-origin configuration includes its isolated port 8001.

The current Starlette/httpx TestClient combination emits a deprecation warning; tests pass. It does not affect the deployed HTTP path. Dependency versions are pinned in the lockfiles.

Not verified: Docker image execution (Docker unavailable), public deployment, hosting latency/load, real email/transfer/upload operations, Luna quality, broad live-model conversation quality, or production healthcare compliance. Live probes are small acceptance evidence, not statistical reliability estimates or universal safety proofs. Reuse these reports for unchanged code/configuration; rerun only when changes affect the relevant checks.

V1 delivery is separated into six reviewable commits: requirements/design, deterministic controller, persistent API/model integration, product UI, browser acceptance tests, and packaging/documentation. Existing verification results are reused when only commit organization changes.
