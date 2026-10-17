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
| P2 | Exhausted document alternatives reported during verification were recorded but not used after verification. | Carry the pending constraint to the first grounded answer; clear it after consumption and across identity/auth/case resets. `backend/controller.py`, `backend/models.py`, `tests/test_conversation_audit.py`. |
| P2 | Revisiting a claim reset its topics and overwrote per-claim summary memory, dropping unresolved receipt questions. | Restore that claim's earlier discussion before adding new topics. `backend/controller.py`, `tests/test_conversation_audit.py`. |
| P2 | Switching directly to another claim while requesting a summary omitted the newly selected claim. | Summarize the union of prior discussed claims and the current authorized claim. Same controller/tests. |

Original defects were reproduced before fixing. Security regressions cover denied reads and sends after role/identity changes, including paused conversations. Conversation regressions cover consumption and all three reset boundaries. No speculative architectural changes or minor cosmetic fixes were added.

## Current backend evidence

- Baseline: **248/248 pytest cases passed** before changes.
- Final backend/policy: **263/263 pytest cases passed**, including existing API, identity, provider, settings, deployment and 23 shared policy scenario cases. Fifteen focused regressions were added.
- CLI: **23/23 scripted policy scenarios passed** independently; same runner used by the Evaluation Lab. These overlap pytest coverage and are not an additional independent sample.
- Tests use temporary stores, scripted/mocked providers and fixed clocks. No real sessions, credentials or data were modified. One existing Starlette TestClient/httpx deprecation warning remains.
- Frontend build passed; browser and final Docker acceptance are recorded below when complete.

## Remaining risks and intentional limits

- No new paid model calls. Historical local acceptance receipts include a 12-call OpenAI synthetic corpus (12/12 checks; 13,139 tokens) and later bounded checks; those are previous runs on previous code, not live acceptance of this revision. Other catalog models, including Claude/Gemini, still need keyed end-to-end acceptance. Fixed-host adapters and malformed/refusal/usage/timeout handling have mocked contracts.
- Identity is synthetic PII matching, with bounded textual role detection; it cannot prove a caller's real identity or representative authority. The Lab and starter deliberately expose fictional examples. No real customer records belong here.
- Summaries and factual responses remain templated. Broad paraphrase quality, actual emotion recognition and human comprehension are not established by offline tests.
- New-session creation is intentionally uncapped by prior owner decision. Operation limits, concurrency limits and a persisted daily token budget remain; disk/traffic abuse protection is limited. Proxy clients can share a rate bucket. Sessions are cleaned lazily, and encrypted historical data may survive in backups/WAL.
- Real email, transfer, claim mutation, payment, appeals and uploads remain outside scope. Production authentication, insurer-approved rules, provider retention arrangements, comprehensive accessibility, native mobile keyboards, load, AMD64 and public restart persistence remain unverified.

The corrected controller is suitable for further synthetic portfolio-demo acceptance. Final readiness depends on the frontend/container checks and on owner review before integration/deployment.
