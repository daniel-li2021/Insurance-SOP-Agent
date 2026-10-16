# V1 implementation

One FastAPI process serves a React/Vite build and same-origin JSON API. SQLite stores encrypted session state; no framework, vector store, queue, or external database is required. The six original fixtures remain unchanged.

## Turn boundary

1. `main.py` checks session ownership, CSRF, origin, request size, deduplication, version, and a durable 45-second lease. It applies persistent rate limits and reserves the model budget before live calls.
2. `interpreter.py` uses OpenAI Responses structured parsing into the Pydantic `Interpretation` schema, with a 30-second overall timeout, no automatic provider retries, no tools, and `store=False`. The endpoint is fixed to OpenAI; callers cannot select endpoints/models. Only the current message and bounded safe context are sent. The offline adapter is a limited regex parser; policy evaluations use explicit scripted interpretations.
3. `identity.py` accepts candidates only when their values have matching source evidence in the current message. Normalization handles explicit dates, phone formatting, case/space differences, and approved stored aliases. Three distinct categories must match one unique person with no active contradiction. Failed verification exposes no partial matching count or fields, and transcript redaction uses supplied extraction/generic patterns rather than fixture membership. Policy number locates/restricts a candidate but never contributes a match.
4. `controller.py` merges provenance, retains early topics/hints, evaluates authorization, resolves authorized cases, renders selected factual guidance, and creates versioned summaries. It can advance multiple ordered transitions in a turn. Emotion selects a short empathetic preamble. Model output cannot declare identity, grant authority, choose arbitrary actions, or generate factual prose.
5. `fixtures.py` validates actual fixture models and is the sole claim read boundary. Every session read checks identity, expiry, party ownership, and representative grant scope. Models and the inspector do not receive the fixture dataset. The explicit synthetic demo-starter endpoint exposes only the assignment's fictional starting identity for reviewer exploration; it is not an account lookup endpoint.
6. `store.py` atomically commits state, responses, audit events, and request fingerprints. Model calls run outside transactions. Stale leases/results cannot overwrite a newer turn. Duplicate committed requests return the current safe view, rather than replaying an old protected snapshot after authorization expiry.

Referenced audit events record their owning party internally and are visible only to that verified party. Legacy events without ownership keep their stored data but hide references in the Playground. Expiry clears claim hints and intent as well as identity, protected messages, summaries, and discussion memory; invalid representative grants also revoke the view.

All private session payloads, including candidates, are Fernet-encrypted at rest. Request fingerprints use keyed HMAC rather than exposing low-entropy identity hashes. Operational access logs contain route/status metadata only. User-facing transcript views redact extracted identity and recognizable credential formats; do not treat redaction as general-purpose PII detection. No analytics or raw prompt logging is installed.

## Consent and representative proof

Representative relationship data provides a hint only. Public chat cannot install a grant. The isolated evaluator binds the supplied status sequences explicitly to representative authorization and injects both an independent mock principal assertion and an expiring `claims:read` grant. That grant omits email scope, which is tested separately. This is not real identity proof and does not authorize the public caller David.

Email uses a separate explicit POST action for Send or Skip, protected by CSRF and authorization. The immutable preview UUID binds its content, masked on-file recipient, and expiry in the stored session; the request cannot supply alternate content or recipient. A new preview has a new UUID. The server rejects expired/stale offers. Successful simulation and receipt are committed in the same transaction, so retries cannot duplicate that simulated action. Failed/time-out simulator branches are available in deterministic evaluations; the public simulator normally succeeds and never contacts an email service.

New questions invalidate all current summaries, including previously simulated-sent previews. The historical send event remains; the next preview has a fresh ID and requires a new choice. Summaries cover the authorized cases actually discussed, using the evidence for each case. No verification credentials appear in a summary. A real email integration would require a durable outbox, recipient verification, provider idempotency, and handling unknown external delivery results; this simulator does not claim those properties for real delivery.

## Grounding and data conflicts

Claim-specific facts and deadlines take precedence over generic follow-up guidance. An expired appeal receives explicit human-review wording, never a newly invented window. `pathology report` maps to the supplied `original pathology report` guidance while preserving its conditional original/scan rule. `office note` maps to `treating provider office note`. Unmapped diagnosis reports use generic guidance. Money uses Decimal and the supplied field meanings. No automatic claim mutation, document submission, or real escalation exists.

## UI and evaluation

React owns rendering and draft input; the backend owns all workflow state. Radix implements main tabs, evaluation tabs, and dialogs, including explicit focus restoration for the mobile inspector. The composer remains fixed while chat and desktop inspector scroll independently. The browser uses the server timestamp to expire visible authorization/consent offers; server checks are authoritative. It immediately hides protected content when authorization expires or a request returns 401, even if its refresh cannot reach the server. Retry retains the request ID and message, and a conflict refreshes the expected state version.

`evaluation.py` is shared by pytest, the CLI, and the Lab. The 23 scenarios check event deltas, explicit action outcomes, locked public views, and deduplication per preview. Runs are isolated, fixed-clock policy tests with sanitized traces and expected/observed assertions. They do not call the live model or modify a customer session. `scripts/evaluate_live.py` is a separate six-call opt-in probe. Live quality is not inferred from deterministic results.

## Operational limits

This is a single-instance demo with lazy retention cleanup, conservative proxy rate limits, bounded model tokens, and no separate worker. All in-flight work can be recovered after its lease expires; previous committed messages survive process restart. Authorization is independently checked after model work and on every action/read. Active grants are evaluator-only, not an externally revocable authorization service. A production system needs real authentication, stronger representative proof, approved retention and insurer rules, real action integrations, and availability/backup procedures.

See the [independent review](RELIABILITY_REVIEW.md) for reproduced findings, Docker evidence, and the proposed targeted live suite. The public starter and Lab intentionally expose fictional fixture examples and must not be used as access paths for real customer data.
