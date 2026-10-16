# V1 verification — October 16, 2026

## Independent review and Docker verification

The current follow-up review passes **59 pytest tests**, including **23 shared policy scenarios**, and the production TypeScript/Vite build. The source changes preserve the existing UI/architecture and fix partial identity feedback, fixture-dependent redaction, representative subject/scope handling, cross-identity audit references, stale sent summaries, expired context, local visibility on expiry/401, and offline claim-date parsing. See the [full classified review](RELIABILITY_REVIEW.md). Meaningful failures were reproduced before fixing them.

**Nine Playwright tests passed against the built Docker image** on localhost port 18080. They cover the complete flow/resume, privacy/injection gate, sent-summary case switching and fresh consent, expiry while refresh fails, HTTP 401 recovery, case ambiguity/Skip, Lab replay, mobile focus/overflow, and network retry. Desktop and mobile screenshots from that container run were visually inspected. The earlier eight-test run against the local backend also passed before the final 401 recovery case was added.

Docker Desktop 4.71.0 / Engine 29.4.1 / Compose 5.1.3 built the supplied multi-stage Dockerfile for **linux/arm64**. Local image tag: `claimflow:v1-review`; image ID: `sha256:fc00c2b232cc3048380df387799671c0b608460b74d5b47ba71f32c92c2948bf`. It was run through the supplied Compose service with an isolated project/volume and a temporary override for loopback port 18080, scripted mode, development HTTP cookies, and no `.env` injection. No OpenAI key was passed into the container.

Container checks passed: root/static UI and health endpoint; explicit Docker healthcheck reporting healthy; nonroot UID 10001; absent `/app/.env` and model key; private volume key permissions; CSRF rejection; authorized denial/summary/Send/deduplication; encrypted session version and simulated receipt surviving a container restart; a date follow-up preserving authorization and removing the old summary; and a new Lab scenario executing in the image. The review test volume was isolated from local `data/` and other Docker projects. After verification it was cleared and a fresh scripted container was left on localhost:18080 for manual exploration. Sanitized aggregate evidence is saved locally in ignored `data/review-verification.json`; the 23 scenario results are in `data/review-policy-evaluation.json`.

The Docker CLI and registry credential helper were installed inside Docker.app but absent from PATH. Adding `/Applications/Docker.app/Contents/Resources/bin` only for the build commands resolved this without changing shell settings. Local browser launches required sandbox escalation for native Chromium permissions; cached browser binaries were reused. No deployment, purchase, or live-model call was made.

The retained six-call live probe below is historical evidence from before this review. Its prompt version and fixture hash were checked against the saved sanitized report. Because verification wording/context changed, it does not certify live behavior of the reviewed version. A proposed **12-call** targeted suite is documented in the review and has not been executed.

Still unverified: AMD64 image execution, public HTTPS/proxy operation, sustained load, dependency vulnerability/advisory scanning, comprehensive accessibility acceptance, broad real-model conversation quality, real insurer authentication/representative proof, and real delivery/integrations. No such production claims are made.

## Original V1 evidence before this review

- **42 pytest tests passed**, including all **19 shared policy evaluation scenarios**. The suite covers source-backed identity candidates, field thresholds, policy-only attempts, aliases/alternate IDs, corrections, early topics, ambiguity, cross-party reads, role changes, deadline precedence, document guidance, monetary distinctions, representative scopes, consent expiry/retries/deduplication, CSRF/origin checks, encrypted persistence, model failure, durable leases, and restart recovery.
- **6 Playwright acceptance tests passed** against a separate offline server: complete denial/summary/Send/resume flow; injection/verification boundary; January ambiguity and Skip; Evaluation Lab replay/reset; mobile inspector focus restoration/no horizontal overflow; network failure/retry with bounded page layout.
- **Production frontend build passed**, including strict TypeScript checking. Main JS is approximately 107 kB gzip; CSS approximately 7 kB gzip.
- **6-call live Sol probe passed** with `gpt-6.1-sol`, prompt `claimflow-extract-v1`, fixture hash `328f5c17f69b`. Run completed at 2026-10-16 08:47 UTC. It used **6,550 total tokens**, with per-call latency **2.8–5.6 seconds**. Cases: partial identity/early document question; remaining identity and retained question; anxiety/payment distinction; wrap-up without Send; injection; unauthorized David. The sanitized reusable report is in ignored `data/live-evaluation.json` on the development machine.
- Manual in-app browser check confirmed the live guided opening, authorized claim response, inspector progression, and summary preview with explicit Send/Skip controls. A preview is saved in `docs/claimflow-preview.jpg`.
- Earlier two-call integration smoke also succeeded for Margaret's full opening and an anxious document-alternative follow-up. Key authentication and model availability were checked without exposing the key.

The browser run found and fixed a mobile dialog focus-restoration defect. Initial browser launches required permission to run Chromium outside the macOS filesystem sandbox; the suite then ran successfully. The test server's explicit allowed-origin configuration includes its isolated port 8001.

The current Starlette/httpx TestClient combination emits a deprecation warning; tests pass. It does not affect the deployed HTTP path. Dependency versions are pinned in the lockfiles.

At that original run, Docker image execution was not verified; the follow-up container evidence above supersedes that limitation. Other original limits: public deployment, hosting latency/load, real email/transfer/upload operations, Luna quality, broad live-model conversation quality, or production healthcare compliance. Live probes are small acceptance evidence, not statistical reliability estimates or universal safety proofs. Reuse these reports for unchanged code/configuration; rerun only when changes affect the relevant checks.

V1 delivery is separated into six reviewable commits: requirements/design, deterministic controller, persistent API/model integration, product UI, browser acceptance tests, and packaging/documentation. Existing verification results are reused when only commit organization changes.
