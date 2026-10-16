# ClaimFlow: investigation and implementation proposal

Design baseline: October 16, 2026. This is the accepted design proposal. V1 is now implemented; see [the implementation architecture](ARCHITECTURE.md) and [validation evidence](VALIDATION.md) for actual behavior, deliberate simplifications, and verification limits.

## 1. Findings from the supplied material

The repository currently contains a minimal README, `requirement.md`, and the six fixtures. There is no application, dependency manifest, test suite, or CodeGraph index. The fixtures and requirements are currently untracked; preserve them and make commits deliberately at reviewed milestones.

All six JSON files parse. A small read-only check confirmed unique party/case identifiers and valid claim/representative foreign keys. This establishes structural consistency, not business completeness.

- [policyholders.json](../insurance_claims/fixtures/policyholders.json): four policyholders, keyed by `party_id`. Two use `national_id_last4`, rather than SSN. Explicit name, phone, and email aliases occur on Ya Wen Li's record; the phone alias duplicates the canonical value. Multiple aliases never count as multiple identity fields.
- [claims.json](../insurance_claims/fixtures/claims.json): five claims; four belong to Margaret/P9, one to Ma Tian/P12. Ava/P7 and Ya Wen Li/P13 have no claim rows. Margaret's January 2026 healthcare denial is CL-2048; January 2025's CL-2011 is closed. `created_at` is the only supplied date for locating a claim, not evidence of a service date.
- [claim_schema.json](../insurance_claims/fixtures/claim_schema.json): descriptive field documentation, **not an executable JSON Schema**. Amounts are USD decimal strings. Build Pydantic validation from the actual records and these meanings; use Decimal, not binary floating point. Status, expected reimbursement, allowed maximum, finalized payment, and fee-schedule amount have different meanings. `net_fee` does not establish what the customer owes.
- [representatives.json](../insurance_claims/fixtures/representatives.json): David is linked to Margaret as her son. There is no representative credential, verified identity, grant, scope, expiry, or authorized delivery address.
- [consent_scenarios.json](../insurance_claims/fixtures/consent_scenarios.json): only `pending → approved` and repeated `pending` sequences. There is no actor, purpose, channel, or binding to David, Margaret, a session, or an email. **The fixtures do not establish which consent these sequences represent.** Use them as generic simulator timing inputs only after adding an explicit purpose in test scenario metadata. They cannot stand in for either a representative grant or the customer's Send decision.
- [required_document_guideline.json](../insurance_claims/fixtures/required_document_guideline.json): default, case-type, document-specific, alternative-document, and follow-up guidance. Claim document keys do not exactly match guidance keys: `office note` needs an explicit mapping to `treating provider office note`; `pathology report` can use the `original pathology report` guidance without asserting that this claim requires an original. `diagnosis report` has no specific guidance and must use the generic fallback. Preserve the original fixture wording and trace every mapping.

CL-2048 records missing pathology and office-note documents, a March 18, 2026 appeal deadline, $0 expected reimbursement, $1,450 allowed maximum, and $0 finalized payment. The deadline is past as of this proposal. The generic instruction to submit within a week must not create a new appeal window. No actual portal URL, mailing address, fax number, upload action, appeal action, or human-transfer integration is supplied.

## 2. Smallest architecture that meets the brief

Use React/TypeScript with Vite, Tailwind, and selected shadcn/ui primitives; FastAPI/Pydantic; and standard-library SQLite. A multi-stage Docker build produces the frontend and serves it from FastAPI on the same origin. One application instance and one Uvicorn worker are sufficient initially.

The runtime path is:

```text
Chat / Send / Skip request
  → session ownership, limits, request deduplication
  → structured interpretation of caller text
  → deterministic memory merge and SOP policy
  → authorized fixture query, when permitted
  → bounded response plan and grounded rendering
  → atomic state, response, and sanitized audit persistence
```

Keep these as small modules in one backend package: validated fixtures, identity matcher, SOP controller, session store, model adapter, response renderer, email simulator, and evaluation runner. They are boundaries for testing, not separate services. No agent framework, vector database, Redis, background worker, or dynamic tool loop is justified by five claims.

The model returns typed proposals: identity candidates with source spans, corrections, role, intent/case hints, emotion, scope classification, requested topics, and clarification needs. It never supplies authoritative `verified`, `authorized`, `phase`, or `sent` values. Validate structure, enums, source attribution, and all referenced records in code. Hallucinated or unsupported identity extraction cannot count toward verification.

For case answers, supply only authorized, necessary evidence. Let the model recommend fact/guidance IDs and conversational paths; render claim facts, monetary values, dates, policy explanations, action results, and summaries from approved data/text. Natural clarification and empathy can vary within a small safe response catalog. **Citations and a second LLM checker do not prove free-form prose is grounded.** If richer factual paraphrasing is introduced later, document its weaker guarantee and evaluate it separately.

Start with ordinary request/response JSON and a visible thinking state. Do not stream unchecked factual prose. Use one interpretation call per normal turn, with at most one additional authorized response-planning call when needed. Bound time, output tokens, retries, and total session spend. Invalid output or a timeout produces a safe recovery response without advancing authorization. A scripted adapter runs deterministic tests and is clearly labeled in the UI.

Configure one live provider initially behind a small adapter: backend-only token and model settings, a deployment-controlled endpoint allowlist, and explicit timeouts. No browser token entry, client-selected model endpoints, arbitrary proxy API, or secret-bearing frontend variables. Choose the actual model through a small quality/latency/cost comparison after deterministic rules exist; this investigation makes no model calls.

## 3. SOP, authorization, and structured memory

The four phases remain the primary state machine. Waiting, error recovery, escalation offered, and completion are substates or outcome flags, rather than extra top-level phases.

```text
VERIFY_ID ──identity + authority──> RESOLVE_INTENT
RESOLVE_INTENT ──unique authorized case + intent──> PROCESS_CASE
PROCESS_CASE ──caller ready to wrap up──> POST_PROCESS
POST_PROCESS ──Send / Skip / expired offer──> completed outcome

PROCESS_CASE → RESOLVE_INTENT: another or ambiguous case
POST_PROCESS → PROCESS_CASE: more questions; invalidate old preview/consent
Any phase → VERIFY_ID: expired/revoked authority; hide protected context
Any phase: offer human assistance or allow exit without claiming a transfer
```

A phase can advance multiple times in one request, but each transition must be evaluated and audited in order. Margaret's opening message can therefore verify, reuse the denied-healthcare-January hint, select CL-2048, and answer without redundant questions. Mentioning only January healthcare produces clarification between CL-2048 and CL-2011 after authorization. No match is a valid outcome; do not invent a claim.

Core invariants:

1. At least three **distinct approved field categories** must match one unique party. Policy/case numbers locate candidates but count as zero fields. Candidate matches across different people cannot be combined.
2. Normalize formats conservatively; accept only explicit stored aliases, never fuzzy identity matches. Ambiguous dates and conflicting active values require clarification. Explicit corrections supersede previous values and trigger recomputation, not an accumulated score. Proposed conservative rule: unresolved identity contradictions block verification even with three other matches.
3. Recommended alternate-ID policy: explicitly allow the fixture's `national_id_last4` for records declaring that type, in the same single identity-number category as SSN last four. This is a proposed business-rule extension to the original SSN-only list, not something inferred dynamically by the model. Otherwise name, DOB, phone, and email remain available.
4. Claim repositories require a server-created, unexpired authorization context on **every** read. Phase alone and knowledge of a `case_id` are insufficient. Filter by authorized `party_id` before returning metadata or details; cross-customer and missing identifiers receive equally non-revealing errors.
5. Before authorization, the model, browser inspector, and responses receive no claim records or expected identity values. Echoing a caller's own claim description must be framed as their report, not confirmation. The frontend bundle must exclude fixtures and raw session state.
6. Representatives need both independent identity assurance and a trusted grant covering the policyholder and requested action. Knowing Margaret's PII, being her son, and appearing in `representatives.json` cannot supply either proof.
7. Sending requires a current summary, authorized recipient, explicit consent, valid authorization, and a unique send record. Neither conversational intent extraction nor fixture `approved` can authorize Send.

**Representative demo boundary:** the supplied data supports the safe refusal/pending/timeout branches, but cannot substantiate successful representative access. Keep the public path fail-closed. To demonstrate success, add a clearly labeled, evaluator-only mock attestation contract using the existing David/P9 relationship: verified representative principal plus scoped, expiring policyholder grant. Bind the status sequences to that mock transaction explicitly; never expose a public “approve myself” switch. This would demonstrate enforcement of trusted assertions, not real representative verification. Preserve the original fixtures. Business approval of that contract is needed before claiming the representative success path is complete.

Session memory should retain:

- Session version, phase/substate, timestamps, ownership, and request IDs.
- Private identity candidates with field type, normalized candidate, source message/span, subject (caller versus policyholder), supersession, and match status. Caller claims and matcher results remain separate.
- Caller role, candidate party, verified principal, grant scope/expiry, and selected case. Customer changes start a fresh protected context; discard old model context and pending consent.
- Intent/case hints, unresolved questions, caller-reported facts, emotion/refusal, scope-attempt streak, discussed evidence, and follow-up items, each with provenance. Emotion is an interaction hint, not a medical inference.
- Versioned summary, recipient reference, consent offer/expiry, decision event, and simulated delivery result.

Use an opaque HttpOnly/Secure/SameSite session cookie; protect mutations with origin/CSRF checks. Persist private session payloads encrypted with a backend-only key, redact identity credentials from persisted transcript views, and set a short configurable retention period. Resume partial verification within that period, but expire authorization separately; protected transcript/history endpoints require renewed authority after expiry. A session identifier alone must not reveal another session.

Proposed demo defaults, to be tested: 15-minute authorization idle timeout, 24-hour session retention, 10-minute summary consent offer, and human-assistance offer after three consecutive out-of-scope attempts. Verification attempt limits also apply across new sessions at the client/IP boundary. These are application defaults, not supplied insurance policy.

## 4. Grounded help, consent, and recovery

Use explicit precedence: access controls → claim-specific facts/deadlines → document-specific guidance → case-type guidance → general guidance. Conflicts become a visible review reason, not silently blended instructions.

- Expired appeal deadline: state the recorded date and that it has passed; offer human review of available options. Do not promise reopening, an exception, or payment. Suppress the generic “within a week” instruction and avoid presenting routine resubmission/review as guaranteed for an expired appeal.
- Missing documents: explain replacements and interim records from the supplied guidance, while distinguishing a possible substitute from an accepted replacement. A pathology scan does not prove originals are unnecessary. Exhausted alternatives lead to human assistance.
- Processing: “usually less than a week” is supplied average guidance after receipt, not a case commitment, payment date, or proof that anything was received. There is no submission/receipt integration.
- Payments: show each requested amount under its actual field meaning. An allowed maximum is not a payout; a denial is not a new payment decision made by this agent.
- Emotion/refusal: acknowledge once, explain the current requirement briefly, offer remaining field choices or assistance, and avoid persuasion loops. Unrelated requests receive a short scope explanation. Mixed messages can still contribute valid identity or intent information.

POST_PROCESS produces a concise preview: discussed claim, recorded status, documents/options, unresolved issues, and follow-up items. Exclude verification credentials. Offer **Send simulated email** and **Skip**, with no preselected choice. Restrict the initial demo to the policyholder's on-file canonical email; show a masked address. A representative's authority to discuss a claim does not imply permission to receive its summary.

The Send endpoint binds consent to `summary_id`, revision/content hash, recipient, actor, authorization, and server expiry. Free-text “yes” never triggers a send in v1; direct the caller to the explicit control when needed. A new question, summary change, recipient change, Skip, or expiry invalidates the offer. Expiry is not Skip and is never approval; allow a fresh preview/offer. A late Send must be rejected server-side even if the browser's timer is stale.

Simulated email success writes a unique receipt atomically with the action and displays “Simulation recorded; no email was delivered.” Failure and timeout use distinct states. Retry the same unchanged operation with its original idempotency key; duplicate Send returns the existing result. For a future real sender, use a durable outbox plus provider idempotency and an explicit unknown-result state; do not promise exactly-once external delivery.

For chat requests, claim a durable per-session in-flight lease with message ID and expected version, perform model work outside the SQLite write transaction, then commit only if the lease/version and authorization are still valid. Serialize conflicting requests or return a recoverable conflict. Cache committed responses by message ID. Expired leases let interrupted turns recover; stale model results cannot overwrite new state. SQLite supports one simultaneous writer, so keep transactions short ([SQLite transaction documentation](https://www.sqlite.org/lang_transaction.html)). No separate queue is necessary for the atomic email simulator.

Audit allowlisted fields only: event ID/time, pseudonymous session, phase transition, decision code, field category/count without values, authorized action, evidence reference/version, model/prompt version, latency, and token usage. Include denied tool attempts. No raw prompts, credentials, transcript bodies, secret values, or chain-of-thought in operational logs. The inspector shows policy reason codes and grounding pointers, not hidden model reasoning.

## 5. Compact product concept

Use two top-level tabs, **Agent Playground** and **Evaluation Lab**, inside a stable viewport. The product should emphasize the conversation and the next required action.

```text
ClaimFlow                         Synthetic data · Live / Scripted
Agent Playground | Evaluation Lab                    New session
Verify identity → Resolve intent → Process case → Follow-up
┌───────────────────────────────────┬─────────────────────────────┐
│ Conversation                      │ Workflow / Decision Inspector│
│                                   │ Verification: 2 of 3         │
│ Authorized fact blocks, when ready │ Intent: denial question      │
│ Inline summary preview             │ Case: locked until authorized│
│ Send simulated email | Skip        │ Latest decision + grounding  │
├───────────────────────────────────┤ Expand sanitized history     │
│ Message input                     │                             │
└───────────────────────────────────┴─────────────────────────────┘
```

The conversation owns the main scroll area; the inspector has an independent scroll area on desktop. Keep header, progress, and composer outside those areas. Use `min-height: 0`/bounded flex containers so page-level and nested scrollbars do not compete. At narrow widths, the inspector becomes a labeled drawer; the conversation remains primary.

Design direction: warm white/slate surfaces, dark navy text, one muted teal accent, restrained amber for attention, and accessible red for failures. System sans typography, 16px body, an 8px spacing rhythm, modest radii, subtle borders, no decorative charts or gradients. Use plain status labels rather than clusters of badges. Lock case context until authorized, and show verification progress without credential values or expected answers.

Support keyboard operation, visible focus, labeled controls, focus restoration for drawers, reduced motion, and adequate contrast. Announce completed responses/status changes politely without stealing focus or announcing every token; this follows [W3C status-message guidance](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html). Pause auto-scroll when the user reads earlier messages and provide “New message.”

Empty state: explain the synthetic scenario and offer safe scenario starters. Loading: indicate the current operation without claiming success. Errors: retain typed input, explain whether retry is safe, and recover the committed session. Human assistance always says “offered” unless an integration confirms an actual transfer.

Evaluation Lab uses a compact scenario list and one selected replay, with a results/trace pane. Show expected versus observed decisions and the first failed invariant. Reset creates a fresh isolated run. Scripted versus live results and model/configuration versions remain visible; passing a scripted scenario is not evidence of live conversation quality. Full live evaluation controls are local/evaluator-only so public users cannot run unbounded paid batches or alter authorization attestations.

## 6. Evaluation strategy and completion evidence

Define scenarios as scripted turns plus expected policy events, forbidden actions, and semantic answer requirements. One runner powers pytest, a CLI report, and the Evaluation Lab. Preserve run artifacts with fixture/configuration hashes so unchanged valid results can be reused.

Deterministic tests use scripted model outputs and a fake clock. Cover the controller, actual guarded repositories/endpoints, memory corrections, fixture validation, and action persistence. Check **absence of unauthorized reads**, not merely absence of leaked text. Representative success tests supply an explicitly trusted mock attestation; the raw fixture alone must fail. Include malicious structured outputs as well as malicious caller text.

Required scenario families:

- Margaret's full opening utterance, incremental identity, mismatches/corrections, refusal, duplicate fields, policy-only attempts, ambiguous dates, aliases, and alternate IDs.
- Early intent reuse; January ambiguity; cross-party case IDs; valid customers without claims; missing/conflicting records; no mutation of fixture status.
- CL-2048 denial/documents, document alternatives and exhaustion, unmatched diagnosis guidance, expired deadlines, processing estimates, and distinctions among all monetary fields.
- David as son/untrusted representative; pending/timeout/approved simulator states; wrong actor, scope, expiry, and grant revocation.
- Frustration and mixed-topic inputs, repeated unrelated requests, prompt injection, malformed model output, model outage, resumed sessions, new customer context, duplicate/concurrent turns, and crashes before/after commit.
- Send/Skip/offer expiry, stale preview, duplicate clicks, retries, simulator failure/unknown timeout, and accidental reuse of representative consent for email.

Use parameterized boundary tests and a few generated event sequences for invariant preservation; avoid padding test counts. Playwright exercises a complete happy path plus verification denial, expired deadline, email consent/retry, session recovery, responsive panels, and keyboard controls.

Live-model runs are opt-in and budgeted: a small fixed corpus of messy paraphrases and adversarial conversations. Hard gates remain deterministic; evaluate empathy, contextual reuse, clarity, and unsupported-assertion rates separately. Human-review representative transcripts; an optional model judge is supporting evidence only. Publish model/prompt/configuration, dates, cost/latency, and failures. Initial acceptance requires every deterministic safety scenario to pass and zero observed unauthorized reads/sends; this is evidence for the tested corpus, not a universal safety claim.

## 7. Deployment recommendation

Prefer **one paid Render Docker web service with SQLite on a persistent disk** for reviewer sessions. The same image runs locally with a mounted data volume. Store model token, session encryption key, and any evaluator access secret in backend environment settings; keep them out of build arguments, images, Git, frontend bundles, and logs.

Budget approximately $7/month for the smallest paid web compute plus $0.25/GB/month for a disk, before model calls, metered overages, and taxes; verify the actual offer before provisioning ([Render pricing](https://render.com/pricing), [Render storage pricing](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses)). A 1GB disk gives a planning estimate of roughly $7.25/month. This is an estimate, not a provisioned quote.

Render Free is useful for disposable previews: it sleeps after 15 idle minutes, takes about a minute to wake, and cannot attach a persistent disk. Local SQLite changes are lost on restarts/redeploys/spin-down, making it unsuitable for the promised durable session demo ([free-service limitations](https://render.com/docs/free)). Paid disks preserve data but restrict the service to one instance and prevent zero-downtime deploys; accept brief deployment interruptions initially ([disk constraints](https://render.com/docs/disks)). Use database-consistent SQLite backups rather than assuming a disk snapshot is a valid database backup. Move to managed Postgres only when multiple instances or stronger availability becomes necessary.

Vercel can run FastAPI, so Python support is not the blocker ([Python runtime](https://vercel.com/docs/functions/runtimes/python)). Its function filesystem provides temporary scratch space rather than durable local session storage; an all-Vercel design needs an external database ([runtime constraints](https://vercel.com/docs/functions/runtimes)). Vercel frontend plus Render API is viable but adds a deployment boundary and cookie/CORS configuration for little benefit here. Hobby is restricted to personal, noncommercial use; Pro currently starts at $20/month, with usage considerations ([Hobby terms](https://vercel.com/docs/plans/hobby), [pricing](https://vercel.com/pricing)). Function cold-start latency also remains workload-dependent; no hosting latency benchmark has been run.

For a public demo: synthetic-data notice, same-origin API, session isolation, bounded input/context, verification limits, session/IP rate limits, server-wide model concurrency and daily token budget reservations, and a kill switch. Persist the global budget so creating sessions or restarting cannot reset it. Public evaluation replay should use scripted results; live runs require evaluator access. No real uploads, email delivery, transfers, appeals, or claim updates in v1.

## 8. Incremental delivery and decisions

1. **Investigation and contract — this proposal.** Fixture relationships checked; ambiguities, policy precedence, UI direction, and deployment constraints recorded. Before security-sensitive implementation, settle alternate-ID approval and the representative mock contract. Safe default for missing grants is denial; do not let this prevent building the policyholder path.
2. **Deterministic vertical slice.** Validated fixture loader, matcher, memory reducer, guarded repository, controller, SQLite state, fake model/clock. Complete when Margaret's flow, corrections, January ambiguity, cross-party access, and expired-deadline rules pass through the API without live model calls.
3. **Early UI slice.** Playground shell, progress, chat, sanitized inspector, error/retry states, summary preview, Send/Skip. Complete when the scripted full workflow is usable at desktop/mobile sizes and through the keyboard. Establish layout before polishing model prose.
4. **Live interpretation and grounded help.** One configured model adapter, structured extraction, evidence-based response planning, empathetic recovery, document alternatives, scope limits, and explicit representative branches. Complete when the small live corpus demonstrates contextual reuse and grounded answers with recorded cost/latency; missing credentials cannot break deterministic tests.
5. **Consent and recovery hardening.** Versioned consent, atomic simulated send, deduplication, concurrent requests, lease recovery, authorization expiry, and retention. Complete when restart/retry/timeout tests cannot create unauthorized access, stale grants, or duplicate simulated sends.
6. **Evaluation Lab and packaging.** Shared scenario runner, expected/observed views, cached run artifacts, focused browser coverage, Docker, configuration example, and setup/architecture/limitations documentation. Complete when a fresh checkout can run the demo and deterministic suite from documented commands without a model token.
7. **Optional hosted delivery and final evidence.** Review configuration and cost before provisioning; deploy only once authorized. Complete with a hosted workflow smoke test, persistent-session restart check, public-budget controls, and a concise results report. Docker delivery remains valid if hosting is deferred.

Update related documentation at each milestone. Stop after its acceptance criteria pass; do not expand into voice, real document intake, real email, general agent tooling, or unrelated infrastructure. Commit/push only as explicitly agreed in the project workflow.

The main improvement to the brief is to make guarantees narrower and demonstrable: a fixture-grounded support conversation, deterministic access and consent boundaries, and an inspectable decision trace. Static PII matching and mock grants are assignment-specific simulations; neither constitutes production healthcare authentication. Real authentication/representative proof, insurer-approved appeal rules, real action integrations, provider data-handling arrangements, and operational availability remain outside the initial demo.
