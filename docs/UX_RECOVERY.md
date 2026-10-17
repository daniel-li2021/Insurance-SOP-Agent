# Verification and conversation recovery — October 17, 2026

Implemented on the existing `main` baseline `8cc064b`. React/FastAPI, the four SOP phases, providers, identity thresholds, authorization, fixtures and simulated-email contract remain in place.

## Verification and safe display

The optional expandable form defaults to Full name + DOB + Phone. Any slot can be replaced with Email or SSN / approved national-ID last four; selections must be distinct. Chat remains available. Inputs display the caller's own values while editing (last four uses a password input), include examples and label DOB as YYYY-MM-DD. They never load stored identity values. Existing guided scenarios remain explicitly fictional.

`POST /api/verify` accepts exactly three approved categories and uses the same CSRF/origin checks, session version, durable lease, HMAC deduplication, turn/attempt limits, identity merge, verification, representative authorization, redaction and audit path as chat. It does not call a model. Submission explicitly corrects only the selected categories; a previously supplied contradictory fourth category still blocks verification. Neither an HTTP success nor three filled inputs establishes authorization. Failure exposes no individual matches. Policy number cannot be selected.

Successful submissions clear the form values; failed network requests retain values in memory for explicit retry. Conversation views continue to show placeholders such as `[name provided]`. This is intentional data minimization, not missing display data: the form is the editable view, and the saved transcript/Inspector do not become identity lookup surfaces. No identity values are put in browser storage.

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

Backend milestone: **181 pytest checks passed**, including 20 focused UX/security cases and all 23 shared scripted policy scenarios (counted within pytest). One existing Starlette/httpx deprecation warning remains. The production TypeScript/Vite build passes. Browser validation and the final UI documentation are recorded in the next milestone.

Runtime sessions, screenshots/traces and keys stay in ignored local output directories. Original fixtures are unchanged. Public deployment, Docker rebuild, real insurer identity/representative proof, real transfer/delivery, human usability and comprehensive accessibility acceptance were not exercised in this batch.
