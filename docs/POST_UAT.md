# Post-UAT refinement — October 17, 2026

The supplied sending-state and summary screenshots take priority over the pasted examples. React, FastAPI, fixture records, authorization and explicit simulated-email consent remain the implementation boundaries.

## Batch 1 — Conversation experience

Responses select the current question, separate appeal deadlines from processing time, narrow document guidance to requested items, and suppress repeated consecutive empathy. Detailed payment fields remain available on request. Safe interpretation context includes recent document focus, without keys or identity values. Early questions survive verification.

The composer clears immediately and shows Sending plus Checking your claim. Only a fixed set of non-identity questions may appear before redaction; all other pending messages use a neutral placeholder. Failures restore the draft; Retry retains the request ID, including after the server commits but its response is lost. Reading position is retained while scrolled up.

Summary uses structured, server-generated claim sections with status, denial reason, payment, deadline, next steps and expandable unresolved limitations. Each claim retains its own facts. Existing transcript answers provide detailed guidance. Recipient, preview expiry, Send/Skip and simulation receipts remain server controlled; preview and claim switching do not send.

Validation: 62 existing controller/API/review tests plus 4 focused regressions passed; frontend build and 3 focused browser journeys passed. These cover question relevance, document pronouns, repeated empathy, per-claim summaries, immediate feedback, redaction placeholder, consent, ID-preserving retry and lost-response deduplication. Chromium required execution outside the filesystem sandbox. Full cross-batch validation follows after settings and evidence changes.

## Batch 2 — Model experience

Private development reuses backend environment keys; settings distinguish the current model, backend default, configured credentials and a connection validated in this session. Missing local credentials select BYOK automatically. `APP_ENV=production` starts offline even with live mode/private environment keys configured, disables local credentials in both UI and server validation, and rejects restored private-key selections. Live public usage requires BYOK. Shared sponsored usage is deferred: existing token budgets are not a spending cap.

The curated catalog now has six OpenAI models, four Claude models and four Gemini models, grouped by provider, with readable names and descriptions. Official structured-output support is documented; every selection must pass the existing probe before it is applied. All six OpenAI IDs are visible to the configured account's Models API (listing is not inference validation). Claude/Gemini account access remains unverified without keys. Only GPT-6.1 Sol has prior bounded conversational acceptance. Other entries explicitly say live acceptance pending. GPT-6.1 Luna is omitted because the official catalog identifies GPT-6 Luna instead. No silent substitution or fallback occurs.

Claude requests now set low effort for extraction and consume the structured text block while discarding thinking blocks, including on always-thinking Opus/Fable models. Schema validation and output/time/token caps remain enforced.

Official references checked October 17, 2026: [OpenAI catalog](https://developers.openai.com/api/docs/models), [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Claude model IDs](https://platform.claude.com/docs/en/models/overview), [Claude structured output support](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Claude effort](https://platform.claude.com/docs/en/build-with-claude/effort), [Gemini IDs](https://ai.google.dev/gemini-api/docs/models), [Gemini generateContent structured output contract](https://ai.google.dev/gemini-api/docs/generate-content/structured-output). Individual older OpenAI model pages also confirm structured outputs: [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

Validation: 95 settings/provider tests passed, including every new catalog ID's mocked request contract and public/private credential separation. Frontend build passed. Browser settings/reset/key-clearing acceptance uses intercepted failures, never a paid call with fake credentials.


## Batch 3 — UI and explainability

Playground answers show collapsible readable evidence labels (for example, Claim CL-2048 record and Pathology report guidance), explicitly identified as synthetic data and supplied guidance. The Inspector shows recent plain-language decisions, current claim/status, Human review recommended, and expandable evidence with original reference paths. Full timestamped event history remains accessible. Evaluation Lab keeps the complete technical trace. No audit events or references were removed from the backend.

The summary follows the supplied white-card reference, including the simulation badge, separated claim/status, red passed-deadline text, prominent recorded payment and clear next steps. Send/Skip remain explicit below the synthetic-action boundary; unresolved limitations remain expandable. An old summary hides during a pending turn so the outgoing bubble and checking indicator remain adjacent, as in the reference. The composer keeps the disabled send arrow while processing.

## Final verification and limits

- Backend: **161/161 tests passed**, including 4 conversation/summary regressions, public-mode credential isolation and contract coverage for every catalog ID.
- Policy CLI: **23/23 scenarios passed**, including authorization, representative scope, explicit consent, expiry, retry and multi-claim summary invalidation.
- Frontend: production TypeScript/Vite build passed; configured provider key bytes were absent from the compiled assets (values were never printed).
- Docker/Chromium: **11/11 browser journeys passed** on the rebuilt Linux/ARM64 image. Covered desktop 1440×1000, mobile 390×844, 320×568, 390×500 and short viewport 720×450, plus desktop summary capture at 1440×1500. Includes pending feedback, no optimistic identity disclosure, restored drafts, same-ID retries, lost-response deduplication, consent, claim switching, expiry, settings/reset/focus behavior, source disclosure and full Inspector history. An initial run had a test-only ambiguous locator matching two evidence rows; narrowing it corrected the test. No application limit was relaxed; full runs used isolated fresh volumes.
- Live: **5/5 GPT-6.1 Sol turns passed**, 6,091 actual tokens, five-call/60,000 reserved-token hard cap, no retries. Responses were read for relevance: denial 73 words, focused alternatives 88, pronoun format follow-up 55, payment 25, late appeal 40. [Sanitized receipt](evidence/post-uat-live.json). Summary preview remained offered with zero email-simulation events. Later summary-reference and visual-only changes were verified offline; no extra paid calls were needed.
- Model discovery: one non-generation Models API read listed all six OpenAI catalog IDs for the configured account. [Access receipt](evidence/post-uat-model-access.json). Listing alone does not prove inference acceptance. Claude/Gemini have official support plus mocked contracts; account access, complete live journeys and real provider failure handling remain unverified without their keys.
- Container: validated offline selection, encrypted conversation and synthetic receipt persisted across restart. Image `claimflow:post-uat`, Linux/ARM64, `sha256:a8338f45d556afd0ab84a8dce50e073a91ad53ffc4be7df0181ff2dfea082f43`. [Verification receipt](evidence/post-uat-validation.json). Health, nonroot UID 10001, absence of `.env` and provider keys, and encryption-key permissions 0600 checked. No dependency or fixture changes.

The optional sponsored demo is **deferred**. Public visitors use BYOK or Offline Demo. Actual mobile software keyboards, native browser zoom, screen readers, sustained load, AMD64 execution and public HTTPS/proxy operation remain unverified. There is no public deployment. The existing Starlette TestClient/httpx deprecation warning remains. Historical 12-call acceptance is retained as historical evidence; it is not relabeled as new validation of the changed prompt.

Reproduce with `.venv/bin/pytest`, `.venv/bin/python -m backend.evaluation --output data/post-uat-policy.json`, `npm --prefix frontend run build`, then `CLAIMFLOW_E2E_URL=http://127.0.0.1:<isolated-port> PLAYWRIGHT_BROWSERS_PATH=/private/tmp/claimflow-browsers npm --prefix frontend run test:e2e`. Use an isolated offline container with no env file/keys and a fresh volume for each full browser run; its real twelve-session/hour allowance includes the reset test. Optional live reproduction: `.venv/bin/python scripts/evaluate_post_uat.py` (five paid calls).

Visual evidence: [summary](screenshots/post-uat-summary.png), [sending state](screenshots/post-uat-sending.png), [desktop workspace](screenshots/post-uat-desktop.png), [mobile summary/actions](screenshots/post-uat-mobile.png). Screenshots were captured from the actual updated offline container and visually inspected against the supplied examples.
