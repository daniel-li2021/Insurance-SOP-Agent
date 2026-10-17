# Final small polish — October 17, 2026

Baseline: `6dbcfc1` on `main`. This pass changes summary spacing/content, document recovery wording, payment-topic retention and the settings form. It adds no provider, action, feature or architecture.

## Summary and settings

Summary vertical padding and gaps are reduced by approximately 17–25%, preserving typography, payment emphasis, claim dividers and Send/Skip controls. A single simulation boundary remains in the preview; the countdown no longer repeats email-delivery wording. “Still unresolved” appears only for a discussed document-receipt question that the demo cannot confirm. A generic no-action disclaimer does not create an accordion on every claim. The generated text summary uses the same condition.

Model settings presents API key entry directly for every live provider. The Credentials selector and local-key choice are removed. Offline Demo, provider/model selection, key clearing/encryption, optional retention, reset confirmation and connection validation retain their behavior. Backend `.env` configuration remains available for local testing/startup; production restrictions are unchanged.

## Document recovery

Document-specific alternatives retain the supplied guidance and source references, with the final conditional human-referral sentence omitted. Once alternatives are exhausted, the response stops repeating those alternatives and gives one caller-facing manual-review recommendation. The expired-deadline paragraph does not add another referral in that response. The offline parser also recognizes hospital/doctor inability wording. Source fixtures are unchanged. No accepted substitute, reversed denial, reopened appeal or real transfer is promised.

## Payment/DOB investigation

The three-turn live baseline (payment for CL-2048 → incorrect DOB with other identity fields → explicit DOB correction) retained `pending_topics=['payment']` and answered the recorded finalized insurer payment after verification. The exact UAT failure was not reproduced live.

A deterministic replay against the baseline controller did reproduce the symptom using a valid interpretation: `intent='payment_question'` with an empty topics list. The controller saved the intent but queued no payment topic; successful verification then defaulted to status/denial. It now uses the payment intent when the topics list is absent. Pending topics are combined with the correction turn’s topics, answered only after authorization and consumed once. Tests cover both explicit and omitted payment topics, DOB-only and full-field corrections, and the actual HTTP verification form. Identity rechecks, expiry, representative restrictions, redaction and protected-context resets remain enforced.

## Validation and limits

- **114 focused backend checks pass** across controller, post-UAT, review, API, settings and UX-recovery modules, including all 23 existing policy scenarios. After the final offline-parser change, the affected 43 post-UAT/API checks passed again. The existing Starlette/httpx deprecation warning remains.
- **Production TypeScript/Vite build passes.**
- **Four distinct local offline Chromium journeys pass:** complete summary/Send/refresh, model-settings reset/navigation, BYOK rejection/key clearing/mobile focus, and combined corrected-payment single/multi-claim summary replacement at 1440×1000 and 390×844. Summary coverage extends the existing replacement journey to retain the full suite’s real session budget. The four focused journeys passed on the final tree. Send/Skip viewport visibility, meaningful accordion display and horizontal overflow are asserted. Screenshots are retained under ignored `data/small-polish/` and `data/v2-model-settings-mobile.png` and visually inspected. Cached Chromium required launch outside the filesystem sandbox; no browser dependency was installed.
- **Five final live GPT-6.1 Sol turns pass** using the local `.env`: payment capture, failed DOB verification without claim reads, corrected DOB with payment answer, useful alternatives once, and exhausted options with one manual-review recommendation. Together with the three baseline calls: **8 calls, 10,117 tokens, no retries**, within an 8-call / 96,000 reserved-token cap. The prompt remains `claimflow-extract-v4`; fixtures remain `328f5c17f69b`. [Sanitized receipt](evidence/small-polish-live.json).

The full backend/browser suites, Docker rebuild, other-provider live calls, real mobile keyboards, public hosting and real insurer operations were not tested in this small pass. The live receipt is bounded synthetic controller acceptance, not general model reliability or production identity assurance.
