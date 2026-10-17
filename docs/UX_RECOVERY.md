# Playground space and key status — October 17, 2026

The main model status now shows a prominent amber **Missing API key** button whenever the backend reports `model_connection.ready=false`. It replaces the Live label and opens Model settings. The existing composer notice remains visible. Offline and configured connections keep their existing status; key presence/validation, provider calls and authorization logic are unchanged.

The four workflow steps now form a vertical rail to the left of the conversation. Desktop shows labels; mobile uses compact numbered steps while retaining accessible labels, current-step semantics and tooltips. The Workflow Inspector stays on the right on desktop and in its existing mobile drawer.

**Expand playground**, in the assistant header, hides the Agent Playground / Claims support heading and removes the remaining top toolbar/padding. Expanded panels begin directly below app navigation. Key status and New session move into the assistant header; the workflow rail extends to the panel height, with a **Back** arrow at its top to restore the heading. Keyboard focus follows the expand/Back control. The workflow, draft and conversation remain available. Expansion is page state only. The input now starts at one row with a 30px minimum text area and tighter vertical padding; the Send target remains 44px and multiline input still uses Shift + Enter.

Validation: the production TypeScript/Vite build and **five focused local offline Chromium journeys pass**: missing-key/settings/expansion, complete summary/Send/refresh, multi-claim summary replacement, mobile inspector/focus/short viewports, and mobile verification form. Assertions cover desktop 1440×1000 and mobile 390×844 expansion, vertical rail placement, draft preservation, restoration, more than 25px of additional conversation height from hiding the heading, input height below 45px, visible status/composer and no horizontal overflow. Existing mobile checks additionally cover 320×568, 390×500 and 720×450. Screenshots under ignored `data/playground-space/` were visually inspected. An initial mobile grid override was corrected; summary controls are scrolled as a group for full visibility.

The top-space follow-up passed the production build and three affected browser journeys again: expansion/key status, mobile inspector, and multi-claim summaries. Additional assertions require the expanded conversation to start within 1px of the app-header bottom, the left rail to match its height, and focus to follow both directions of the toggle. Desktop and mobile screenshots were inspected after this adjustment.

No backend behavior changed, so prior backend evidence is reused. No new paid API calls, full suites, Docker rebuild or public deployment were run. Real mobile keyboards remain unverified.

---

# Playground transcript display — October 17, 2026

The backend privacy policy, identity parser, verification rules, authorization checks, audit events and persisted transcript are unchanged. Playground keeps a separate React state map of the page's own submitted text keyed by the confirmed user-message/request ID. Manual chat and Guided Scenario show the original submitted message; Optional Form shows labeled values from precisely the submitted fields. Nothing is reconstructed from fixtures, historical messages or verification results. Unrecognized and incomplete identities can display their own submitted text too.

Pending identity messages remain hidden until confirmation. A lost-response retry uses the same request ID and displays the original once, only after confirmation. The map never enters the server session object, request bodies, browser storage, saved transcript, Inspector or audit events. Existing retry drafts remain in memory under the existing recovery behavior.

**Hide submitted details** discards the display map and immediately uses backend redaction. A later submission can display its own new text. Refresh starts with no map. New Session, successful model reset, authorization expiry (including failed refresh), identity recheck, representative blocking and 401/403/409 recovery clear originals. The map is scoped to the session CSRF token, model and latest authorization-reset event to prevent old originals appearing in another context. Other tabs receive only redacted history.

## Focused validation

**27 distinct Chromium journeys pass**: six new transcript journeys plus all 21 existing workflow/recovery journeys. The new checks cover the exact Margaret Chen acceptance message, confirmation-ID mismatch, unknown identity values without verification, Guided Scenario, Optional Form mismatch/correction, Hide on mobile, page refresh, another tab, New Session, model reset, identity recheck and lost-response idempotent retry. Existing expiry coverage now also asserts local originals disappear when authorization expires and the refresh fails. API session responses, Inspector content and localStorage/sessionStorage remain free of the submitted identity values. Sources, Summary Send/Skip, assistance controls and Evaluation Lab pass their existing browser journeys.

The production TypeScript/Vite build and **five focused backend redaction/form/representative/expiry regressions pass** (28 unrelated cases deselected). Desktop (1440×1000) and mobile (390×844) screenshots are saved under ignored `data/` and visually inspected; message viewport assertions explicitly check that original submitted text can be seen. Browser tests reuse `/private/tmp/claimflow-browsers`; Chromium required execution outside the filesystem sandbox. These are synthetic local offline checks; no paid model call, full backend suite, Docker rebuild or public deployment was run. The existing Starlette/httpx deprecation warning remains.

---

# Identity UX refinement — October 17, 2026

## Investigation and root causes

Baseline `2651d4b` on `main`, prompt `claimflow-extract-v3`, fixtures `328f5c17f69b`: fresh self-service HTTP sessions verified the exact Margaret Chen Name + DOB + Phone supplied in the request, in both structured and natural-language live messages. All three Live Interpreter candidates had literal supported sources and caller subjects. The form also verified the same fixture without a model call. Two baseline live calls used 2,516 tokens. The reported failure with those exact inputs could **not** be reproduced in a fresh session; there is no evidence to attribute it to backend fixture matching or to redaction.

Confirmed related failures: `03/15/1985` and `March 15th, 1985` were omitted by the offline parser and rejected by DOB normalization. The optional form enforced ISO alone. This prevented common equivalent date formats from contributing a matching category. A prior representative interaction also deliberately kept the role sticky, so even fully matching policyholder details could not authorize that session. A new session clears that role; a page refresh resumes it. Individual matching fields remain undisclosed before authorization.

## Current behavior

- The shared deterministic extractor supplements categories omitted by an interpreter with literal caller spans. It never replaces a model-supplied category, guesses a value, or reads fixtures. Source support and normalized equality still govern every candidate. Scripted mode uses the same extractor. Safe model context now includes the representative-mode flag.
- DOB accepts ISO/year-first separators, unambiguous US numeric dates, spelled-out full/abbreviated months, ordinal days and ordinary punctuation. `03/04/1985` needs clarification; invalid dates remain blocked. Phone accepts US formatting and optional `+1`, email trims surrounding whitespace and case-folds, and ID last four supports “SSN ending in 4472.” Names still use exact normalized strings or explicit fixture aliases, with no fuzzy matching.
- Distinct contradictory values in a turn remain blocked even on a correction turn. Ambiguous/invalid supplied fields cannot be ignored to authorize using other fields. Explicit corrections or the form can resolve conflicts. Existing three-category, same-person, all-supplied-fields, ID-type, representative-grant and expiry controls remain enforced.
- **Use synthetic verification details** is labeled Demo only and reads the existing P9 fixture through the existing synthetic starter endpoint. It fills Name + DOB + Phone, remains editable, and never submits or authorizes. The explicit action is now **Verify details**. Chat remains supported independently. Desktop fields align in three columns; mobile stacks them, with inherited theme fonts, spacing, borders and buttons.
- Backend transcript placeholders are retained. Playground now temporarily overlays confirmed locally submitted text as described below. Privacy labels in saved history still do not indicate extraction or verification results. New formats remain redacted independently of provider output.
- A persistent Representative Mode panel explains the extra authorization requirement and opens the existing reset confirmation via **Start fresh self-service session**. Details cannot silently switch a representative into a self-service caller.
- Chat, Inspector and Lab sources were **not removed** by the earlier simplification commit `8cc064b`: readable chat labels replaced raw strings, while internal references and audit events remained. The chat disclosure now explicitly says **Sources**. Inspector retains its evidence table and complete history; Evaluation Lab Decision Trace retains original references and timestamps. Pure empathy and unauthorized responses acquire no invented references.
- While paused, the textarea and Send control are disabled, and the panel directs the caller to **Return to chatbot**. Direct API submissions of ordinary paused messages receive 409 before inference or state mutation. Repeated human requests retain the existing single escalation acknowledgment. Resume preserves conversation/verification subject to normal expiry; escalation remains simulated guidance without transfer, tickets or queues.

## Model key flow and compatibility changes

Users select a provider/model, enter a key in Model settings, and choose **Validate & apply**. The existing small paid validation call and conversation reset still apply. Production mode still requires BYOK for a live model; Offline Demo works without a key. Private local configured keys remain available only outside production.

**Keep this key for new sessions in this browser** is optional and unchecked. The encrypted backend connection is copied into a new cookie-bound session only when selected; identity, representative state, transcript, claim context and consent are never copied. The old session row is deleted. No key enters localStorage/sessionStorage or public responses. The normal 24-hour inactivity/cookie limit applies, and another browser does not inherit the key. Uncheck and apply (with the normal key revalidation) to stop retaining it; applying Offline Demo also removes it.

Previously, every reset discarded BYOK and silently returned to the backend default. Without opt-in, reset now deletes the key but preserves the BYOK provider/model selection so it can explicitly show **Missing key — no API call**. The backend rejects a subsequent model turn before creating an adapter or reserving model tokens. Users can enter a new key or select Offline Demo. Retained connections reuse their existing validation timestamp; reset itself makes no paid call. Form verification and explicit assistance controls do not require a model key.

These behavior changes were communicated before edits. Existing rate limits, model-switch reset/confirmation, encrypted persistence, idempotency and CSRF checks are preserved.

## Validation

**229 pytest checks pass**, including all 23 existing scripted policy scenarios. Production TypeScript/Vite build passes. **21 distinct local Chromium journeys pass**, using the existing regression suite plus Sources/autofill/representative reset and missing-key notice coverage. A pause test helper was updated to expect a disabled composer; its corrected case and final form/settings controls were rechecked separately. Desktop (1440×1000) and mobile (390×844) form screenshots were visually inspected; generated images remain ignored under `data/`.

The five-call final live HTTP acceptance passes structured input, natural US DOB/phone formatting, identity accumulated over two messages, and an ambiguous DOB withheld despite three other matching fields. It uses `gpt-6.1-sol`, prompt `claimflow-extract-v4`, fixtures `328f5c17f69b`, **6,321 tokens**, no retries and a 60,000-token reservation cap. Including the two baseline calls, this task made seven paid calls using **8,837 tokens**. See [sanitized evidence](evidence/identity-ux-live.json) and [opt-in runner](../scripts/evaluate_identity_ux.py). These are bounded synthetic observations, not general model/identity reliability.

Key retention, removal, browser isolation, restart, expiry and absence of provider calls without a key are tested with mocked providers; no real customer key was submitted to settings in these tests. The missing-key browser notice uses a mocked session response; real persistence is exercised through backend HTTP tests. Native Chromium needed execution outside the filesystem sandbox. The existing Starlette/httpx warning remains. No public deployment, Docker rebuild, other-provider live acceptance, production identity proof, or real transfer/delivery was performed.

---

# Earlier verification and conversation recovery — October 17, 2026

Implemented on the existing `main` baseline `8cc064b`. React/FastAPI, the four SOP phases, providers, identity thresholds, authorization, fixtures and simulated-email contract remain in place.

## Verification and safe display

The optional expandable form defaults to Full name + DOB + Phone. Any slot can be replaced with Email or SSN / approved national-ID last four; selections must be distinct. Chat remains available. Inputs display the caller's own values while editing (last four uses a password input), include examples and label DOB as YYYY-MM-DD. They never load stored identity values. Existing guided scenarios remain explicitly fictional.

`POST /api/verify` accepts exactly three approved categories and uses the same CSRF/origin checks, session version, durable lease, HMAC deduplication, turn/attempt limits, identity merge, verification, representative authorization, redaction and audit path as chat. It does not call a model. Submission explicitly corrects only the selected categories; a previously supplied contradictory fourth category still blocks verification. Neither an HTTP success nor three filled inputs establishes authorization. Failure exposes no individual matches. Policy number cannot be selected.

Completed submissions clear and collapse the form so the response stays visible; failed network requests retain values in memory for explicit retry. Conversation views continue to show placeholders such as `[name provided]`. This is intentional data minimization, not missing display data: the form is the editable view, and the saved transcript/Inspector do not become identity lookup surfaces. No identity values are put in browser storage.

Refusing SSN now explains that Name + DOB + Phone or another approved three-field combination is accepted. Later incomplete attempts use a shorter reminder rather than repeating the entire field list. Ambiguous numeric DOB input receives a format clarification.

### Scripted parsing versus live interpretation

Before changes, the offline parser captured DOB and Phone but missed Name in lowercase `my name is margaret chen` and curly-apostrophe `I’m Margaret Chen` introductions. It also omitted abbreviated birth months despite normalization already supporting them. Labeled names now accept case differences, the existing self-introduction pattern accepts curly apostrophes/semicolon separators, and explicit abbreviated birth dates and `last four digits` are recognized. Claim dates still cannot silently become DOB; numeric date ambiguity still fails closed.

Live interpretation does not use that regex parser. Its existing source-evidence/normalization gate already supports Name + DOB + Phone; a mocked live response verifies that canonicalized DOB and formatted phone can pass, while an invented source cannot. The shared extraction prompt now explicitly recognizes this combination, SSN optionality, lowercase/curly introductions, and transfer requests. **No paid live calls were made.** This investigation proves the scripted failures and the live contract, not an empirical live-model defect or broad live quality. Existing live receipts are historical and do not certify prompt `claimflow-extract-v3`.

## Human assistance, simulation only

A minimal `assistance_paused` flag is independent of SOP phase and authorization. An explicit human request receives one acknowledgment, explains that no real transfer/ticket is possible, and recommends official insurer member support. The panel supplies no invented contact information or queue state. Repeated requests and acknowledgments are retained without repeating the assistant's transfer paragraph or verification instructions. The caller explicitly chooses Return to chatbot (or the supported equivalent chat command); existing context survives. Expiry still revokes access normally.

Explicit pause/return controls work without live inference, including provider failure and identity-attempt lockout. They cannot read claims, clear attempt counters or bypass verification. Turn and transport limits still apply. Existing Summary Preview, Send/Skip, consent expiry, safe retries and simulated receipts are unchanged; paused chat hides summary action controls. Acknowledgments while paused never send email. No real email or support integration was added.

## New Session investigation

Reproduced before changing the session code:

- Resetting a session with a shared browser cookie leaves another tab's old CSRF token behind. Its next mutation returns **403**. The UI previously recovered **409** versions only; it now reads the current session on either response, without replaying the action. A replaced session discards the old pending operation and preserves the chat draft for review. Same-session version changes offer an explicit retry using the current version and original request ID.
- The 13th creation in an hourly bucket returns **429**; refresh does not clear that persistent allowance. The response previously said only “Too many requests” with a fixed 60-second retry header. It now explains the **12/hour** limit, time remaining to the actual bucket boundary, and retention of the current session. `Retry-After` reflects that boundary. The limit is unchanged and is keyed to the transport client address, so a proxy can cause clients to share it.
- Failed initialization left New Session disabled because there was no session object. It now becomes available after initialization fails. While initialization is still pending, creation stays disabled to prevent competing session-cookie responses.

Source inspection also found that bootstrap cached a completed session snapshot indefinitely. It now caches only the in-flight initialization promise, preserving React StrictMode deduplication. Older background refreshes cannot overwrite a newer operation's state. Recover explicitly synchronizes; a failed read no longer silently creates a replacement session. A failed summary-expiry read is attempted once, rather than every second indefinitely.

Existing **401** recovery locks protected content and permits an explicit new session. Backend tests cover 24-hour session expiry and cookie persistence; browser regressions retain authorization-expiry hiding, safe network retry and explicit reset confirmation. No forced reload, automatic mutation retry, limit increase or state-clearing workaround was introduced.

## Validation

**181 pytest checks passed**, including 20 focused UX/security cases and all 23 shared scripted policy scenarios (counted within pytest). **19 Chromium browser journeys passed** on isolated offline servers: the 11 existing workflows plus eight recovery/form cases. The final form-collapse adjustment received a focused browser recheck. The production TypeScript/Vite build passes. The mobile expanded form was visually inspected at 390×844; it remains inside the scrolling conversation with the composer available. These are local developer checks, not public-hosting or comprehensive usability/accessibility acceptance.

Browser checks include generic mismatch/correction, conflicting earlier fields, alternate fields, redaction, human-request repetition/persistence/voluntary return, stale-CSRF replacement, stale-version explicit retry, rate-limited reset preserving context, recovery after failed initialization, and a single summary-expiry synchronization attempt under network failure. Suites use independent temporary databases on ports 8001/8002 so the real 12/hour limit is tested without weakening it. Initial local Chromium launches needed filesystem-sandbox escalation; one form-label accessibility mismatch was corrected, and subsequent browser failures were test locator/timing issues. One existing Starlette/httpx deprecation warning remains.

Reproduce with `.venv/bin/pytest`, `npm --prefix frontend run build`, then `cd frontend && npm run test:e2e` (reuse the installed Chromium cache if configured). No live model calls or Docker rebuild are required for these checks.

Runtime sessions, screenshots/traces and keys stay in ignored local output directories. Original fixtures are unchanged. Public deployment, Docker rebuild, real insurer identity/representative proof, real transfer/delivery, human usability and comprehensive accessibility acceptance were not exercised in this batch.
