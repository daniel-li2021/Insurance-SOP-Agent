# Post-UAT refinement — October 17, 2026

The supplied sending-state and summary screenshots take priority over the pasted examples. React, FastAPI, fixture records, authorization and explicit simulated-email consent remain the implementation boundaries.

## Batch 1 — Conversation experience

Responses select the current question, separate appeal deadlines from processing time, narrow document guidance to requested items, and suppress repeated consecutive empathy. Detailed payment fields remain available on request. Safe interpretation context includes recent document focus, without keys or identity values. Early questions survive verification.

The composer clears immediately and shows Sending plus Checking your claim. Only a fixed set of non-identity questions may appear before redaction; all other pending messages use a neutral placeholder. Failures restore the draft; Retry retains the request ID, including after the server commits but its response is lost. Reading position is retained while scrolled up.

Summary uses structured, server-generated claim sections with status, denial reason, payment, deadline, next steps and expandable unresolved limitations. Each claim retains its own facts. Existing transcript answers provide detailed guidance. Recipient, preview expiry, Send/Skip and simulation receipts remain server controlled; preview and claim switching do not send.

Validation: 62 existing controller/API/review tests plus 4 focused regressions passed; frontend build and 3 focused browser journeys passed. These cover question relevance, document pronouns, repeated empathy, per-claim summaries, immediate feedback, redaction placeholder, consent, ID-preserving retry and lost-response deduplication. Chromium required execution outside the filesystem sandbox. Full cross-batch validation follows after settings and evidence changes.
