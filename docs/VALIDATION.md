# ClaimFlow review and validation

Reviewed October 17, 2026 against GitHub main `9bb61be124aca32210bc7549f6b18b708d486b07`, confirmed through the connected GitHub API. The review branch contains focused corrections; main and the hosted service are unchanged. Three independent reviewers covered authorization, conversation/Bonus behavior, and frontend/session reliability; the lead reproduced important security cases and integrated the changes.

## Assignment and Bonus coverage

| Requirement | Assessment |
| --- | --- |
| Four ordered SOP phases | Implemented and covered by shared policy scenarios and HTTP journeys. Early context does not authorize reads. |
| Three distinct approved identity fields | Deterministic matching for one policyholder; policy number excluded, conflicts fail closed, no partial-match feedback. Optional form uses the same gate without a model call. |
| Authorization, privacy, representatives | Per-read party/expiry checks; cross-policyholder claims denied. Representative relationships and chat assertions cannot create grants. Public representative flow remains locked; successful grants are evaluator-only. |
| Early memory, ambiguity, grounded reasoning | Retains intent, claim hints, pending questions and document constraints; asks before choosing ambiguous records. Facts, money meanings and expired deadlines come from fixtures. |
| Summary and explicit Send/Skip | Current preview, on-file recipient, expiry, deduplication and fresh consent. Cross-claim summaries preserve discussion and unresolved receipt questions. Sending is simulated. |
| Scope rejection and repeated retries | Polite redirection and human-support offer; explicit human requests pause assistance without a real transfer. |
| Emotional support / SOP recovery Bonus | Bounded empathy for frustration, anxiety, confusion and refusal; explains privacy, offers alternate fields and human support without bypassing gates. Not a general emotion-recognition benchmark. |
| API token, text UI, full workflow, delivery | BYOK settings and a React Playground/Inspector/Lab; Docker source and setup satisfy the repository delivery alternative. The README records a previously published demo; this review neither deployed nor retested it. |

Offline parsing is limited and responses use deterministic templates. Passing policy tests establishes the tested controller behavior, not broad live language quality or production identity assurance.

## Confirmed findings, ordered by severity

No P0 was confirmed in this review. This is not a proof that none exists.

| Priority | Confirmed issue and root cause | Correction and affected files |
| --- | --- | --- |
| P1 | Human-assistance early returns ran before caller-role and identity revocation. A verified caller could identify as another person or an unauthorized representative and retain protected history and an active summary. | Apply sticky representative detection and expire incompatible access before pause/resume; evaluate conflicting literal identity on the pause path without granting new access. `backend/controller.py`, `backend/identity.py`, `backend/interpreter.py`, `tests/test_security_audit.py`. |
| P1 | Explicit third-party friend/client/patient identity could be treated as self-service by the offline parser. | Shared bounded representative cues protect both interpreter and controller; incidental friend mentions do not block self-service. Same files and regressions as above. |
| P1 | A delayed, already-committed turn response could restore protected transcript content after another tab reset the session and the Lab synchronized it. Backend access was revoked, but the browser accepted the stale response. | Invalidate the operation epoch when synchronizing and ignore superseded success/error/finally updates; preserve the unfinished message as a draft. `frontend/src/App.tsx`, `frontend/e2e/ux-recovery.spec.ts`. |
| P2 | Exhausted document alternatives reported during verification were recorded but not used after verification. | Carry the pending constraint to the first grounded answer; clear it after consumption and across identity/auth/case resets. `backend/controller.py`, `backend/models.py`, `tests/test_conversation_audit.py`. |
| P2 | Revisiting a claim reset its topics and overwrote per-claim summary memory, dropping unresolved receipt questions. | Restore that claim's earlier discussion before adding new topics. `backend/controller.py`, `tests/test_conversation_audit.py`. |
| P2 | Switching directly to another claim while requesting a summary omitted the newly selected claim. | Summarize the union of prior discussed claims and the current authorized claim. Same controller/tests. |
| P2 | Settings retained a stale CSRF token/version after another tab reset or changed the conversation, causing repeated Apply failures. | Synchronize only when state actually changed, clear stale consent and require explicit re-apply; preserve drafts. `frontend/src/ModelSettings.tsx`, `frontend/src/App.tsx`, `frontend/e2e/ux-recovery.spec.ts`. |
| P2 | Evaluation Lab repeatedly failed after another tab replaced the session. | Synchronize the current session on stale-CSRF failure and require explicit rerun; no automatic action replay. `frontend/src/App.tsx`, `frontend/e2e/ux-recovery.spec.ts`. |
| P2 | Header/navigation geometry changed between Playground and Lab at responsive breakpoints. | Integrate the pre-existing fixed mode slot and shared header sizing; retain mounted workspaces. Six viewport geometry cases and two state/scroll roundtrips cover it. `frontend/src/App.tsx`, `frontend/src/styles.css`, `frontend/e2e/workflow.spec.ts`. |

Original defects were reproduced before fixing. Security regressions cover denied reads and sends after role/identity changes, including paused conversations. Conversation regressions cover consumption and all three reset boundaries. No speculative architectural changes or minor cosmetic fixes were added.

## Validation evidence

- Baseline: **248/248 pytest cases passed** before changes.
- Final backend/policy: **263/263 pytest cases passed**, including existing API, identity, provider, settings, deployment and 23 shared policy scenario cases. Fifteen focused regressions were added.
- CLI: **23/23 scripted policy scenarios passed** independently; same runner used by the Evaluation Lab. These overlap pytest coverage and are not an additional independent sample.
- Tests use temporary stores, scripted/mocked providers and fixed clocks. No real sessions, credentials or data were modified. One existing Starlette TestClient/httpx deprecation warning remains.
- Production TypeScript/Vite build passed. Final JS asset: `index-B8s7y3vu.js`.
- **34/34 distinct Chromium journeys passed across isolated final project runs**: recovery 14/14; workflow/transcript 20/20; final conflict/delayed-response regressions were also rerun 2/2 after the nested catch guard. This is not a claim of one final monolithic run. An earlier run passed 32/33; its sole failure was an outdated Inspector source-label assertion, corrected to the existing readable label while retaining raw-source checks in the technical trace.
- Switching coverage: six responsive header-geometry cases and desktop/mobile roundtrips preserve draft, transcript, chat/evidence scroll, expanded layout, selected scenario and open trace. Current desktop/mobile screenshots were visually inspected; screenshots and runtime reports stay local unless deliberately selected for publication.
- Final **Linux/ARM64 Docker build and production-profile smoke passed** on loopback with no `.env` or provider credentials: UI/hashed assets (including the exact final JS), health, Secure/HttpOnly/SameSite cookie, trusted origin/CSRF rejection, disabled owner keys, private/schema paths, complete verify→summary→Send simulation, duplicate-send receipt, and representative revocation/send denial. The verified encrypted session and receipt survived container restart. Health was healthy; UID 10001; key mode 0600.
- Tested image: `claimflow:focused-review`, image ID `sha256:95221095d3414f4499be87e4b27125ea7b48d192f9355f4fa65bc83805e77b39`. Container HTTP used manual Secure-cookie forwarding only in the isolated harness; Chromium journeys ran against separate local offline servers, not this container. Public TLS/proxy behavior was not tested here. The disposable container/volume were removed afterward.

Reproduce backend, policy, frontend and browser checks from the repository root:

```sh
.venv/bin/pytest
.venv/bin/python -m backend.evaluation --output data/policy-evaluation.json
npm --prefix frontend run build
cd frontend
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/claimflow-browsers npm run test:e2e
```

Use an installed Chromium path appropriate to your machine (or `npx playwright install chromium`). The provided Playwright config starts isolated offline servers/stores. Docker verification uses `docker build -t claimflow:focused-review .` and a disposable production-profile container with a fresh volume, exact test origin and no `.env` injection.

## Remaining risks and intentional limits

- No new paid model calls. Historical local acceptance receipts include a 12-call OpenAI synthetic corpus (12/12 checks; 13,139 tokens) and later bounded checks; those are previous runs on previous code, not live acceptance of this revision. Other catalog models, including Claude/Gemini, still need keyed end-to-end acceptance. Fixed-host adapters and malformed/refusal/usage/timeout handling have mocked contracts.
- Identity is synthetic PII matching, with bounded textual role detection; it cannot prove a caller's real identity or representative authority. The Lab and starter deliberately expose fictional examples. No real customer records belong here.
- Summaries and factual responses remain templated. Broad paraphrase quality, actual emotion recognition and human comprehension are not established by offline tests.
- New-session creation is intentionally uncapped by prior owner decision. Operation limits, concurrency limits and a persisted daily token budget remain; disk/traffic abuse protection is limited. Proxy clients can share a rate bucket. Sessions are cleaned lazily, and encrypted historical data may survive in backups/WAL.
- Real email, transfer, claim mutation, payment, appeals and uploads remain outside scope. Production authentication, insurer-approved rules, provider retention arrangements, comprehensive accessibility, native mobile keyboards, load, AMD64 and public restart persistence remain unverified.

## Documentation and demo readiness

**Ready for owner review as a synthetic portfolio demo**, with the Assignment and Bonus covered within the boundaries above. No main merge, hosted deployment, production change or new paid model call occurred. Live conversational acceptance of this revision is still pending.

Public documentation is reduced to README, the original assignment, the main plan, architecture, usage, deployment, this review and third-party notices. All six supplied JSON fixtures moved to `docs/fixtures/` without byte changes; the original assignment moved to `docs/ASSIGNMENT.md` unchanged. Backend, Docker and private-path tests use the new location. Four selected screenshots remain tracked. Superseded proposals, intermediate implementation notes, raw historical receipts and extra images are untracked and ignored while remaining local; previous commits retain their history. The optional identity-UX script now writes to ignored `data/` and creates its output directory on a fresh checkout.

P3 cosmetic refinements, broad response rewriting and new infrastructure were intentionally deferred. Existing limits are retained; this acceptance is not a production security certification.
