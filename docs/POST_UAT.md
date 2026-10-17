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
