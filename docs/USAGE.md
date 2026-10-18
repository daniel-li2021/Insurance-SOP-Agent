# ClaimFlow usage and configuration

Detailed local setup, Playground behavior, model settings, verification and operating limits. For public hosting, use the [Render deployment guide](DEPLOYMENT.md). For a short introduction, see the [README](../README.md).

## Run locally

Requires Python 3.11+ and Node 22. The Python and frontend lockfiles record tested versions.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm --prefix frontend ci
npm --prefix frontend run build
# Only for a new setup; preserve any existing .env:
cp -n .env.example .env
.venv/bin/python -m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8000
```

Open [localhost:8000](http://localhost:8000). Choose **Try a guided scenario** for Standard Claim, Frustrated Caller, or Ambiguous Claim. Each inserts an editable synthetic opening without sending it. The frustrated scenario includes expandable identity details for continuing after the privacy gate. Or type a conversation. **New session** asks for confirmation when there is a conversation or unsent draft. Review the summary to explicitly Send a simulation or Skip. No real email is delivered.

The composer clears immediately, shows a pending message and checking indicator, and restores the draft on failure. Pending identity-bearing messages stay hidden until the server confirms their request ID; Retry reuses that ID. Playground then displays your own submitted text from page memory, including Guided Scenario and Optional Form values, without requiring successful verification. **Hide submitted details** forgets these local originals. Refresh, New Session, model reset, authorization expiry/recheck and security/version recovery return to safe redacted history. Originals are never added to browser storage, backend transcript records, audit events or the Inspector. Responses focus on the current question. Summaries separate each claim and retain explicit Send/Skip. Playground sources use readable labels; the Inspector shows readable evidence source names and concise decisions, with original references retained in complete timestamped history. The Evaluation Lab retains its full technical trail.

The Evaluation Lab uses a compact scenario header with actions beside the workflow description on wide screens. Its scripted/no-model-call badge sits in the top application header while the Lab is active, leaving the subtitle clear. Navigation geometry stays fixed when switching workspaces; drafts, chat scroll and Lab results remain mounted.

The four workflow steps sit to the left of the conversation. **Standard mode** keeps the heading, three guided scenario cards (one compact picker on narrow screens), assistant title and SOP guidance, form access, and desktop Workflow Inspector visible. Scenarios stay accessible during the conversation. **Prefer a form?** is a compact inline section below the scenarios; open it to edit verification fields without scrolling through messages. The form area scrolls when needed and stays bounded so the composer remains visible, including on short screens.

Use **Expand playground** in the assistant header for a taller, wider conversation. The heading is hidden, the workflow rail becomes numbered steps, and scenarios and form access become compact controls. Model status and New session move into the assistant header; a missing-key warning stays accessible. The initial welcome is hidden in expanded mode once there are conversation messages. The **Back** arrow restores standard mode; draft messages and form values survive toggling. The composer stays fixed, with independent conversation/inspector scrolling. Mobile uses an inspector drawer.

**Suggested prompts** come from the current verified state, selected claim/status, and summary availability. Before verification they offer a status question, an information question, or opening the form. After claim selection they offer a denial/status question, documents, and next steps; the authorized claim-choice buttons guide ambiguous selection. Summary-stage suggestions also offer asking about another claim. Text chips replace the composer draft and focus it for review; they never send a turn, call a model, or trigger a summary action. Suggestions hide during pending operations, errors, human-support pause, or missing-key state. **Review summary** and the explicit **Send simulated email / Skip** controls keep their existing behavior. The chat input starts at one line, with Shift + Enter for line breaks. See [current validation](VALIDATION.md).

During verification, **Prefer a form?** optionally accepts three distinct details, defaulting to Full name + DOB + Phone. Email and SSN / approved ID last four are alternatives; SSN is optional. **Use synthetic verification details** (Demo only) fills editable Margaret Chen fixture values without submitting them; select **Verify details** explicitly afterward. The three fields sit inline on desktop and stack on mobile using the existing theme. The compact form keeps demo autofill at the upper right, uses placeholders with screen-reader labels, and offers **Clear** to empty only the current form values without changing verification state or field selections. Date-format guidance remains available to assistive technology. Values are visible while editing and temporarily in your confirmed Playground message; saved conversation history remains redacted; redaction labels describe privacy, not match results. The same backend rules must verify all supplied details against one policyholder. Chat accepts ISO/unambiguous US numeric/spelled-out DOB, formatted US phone numbers, normalized email, and “SSN ending in …”; ambiguous or contradictory values need correction. Representative Mode remains active until a fresh self-service session is started. Human requests pause assistance with a clear simulation-only panel and **Return to chatbot**; normal message submission is disabled while paused. New Session has no hourly creation cap; stale-tab security/version recovery synchronizes without automatically replaying an action. Settings requires fresh reset consent after synchronization, and the Lab requires an explicit rerun. A delayed response from the replaced session cannot restore its protected transcript; an unfinished message remains a draft. See [current validation](VALIDATION.md).

For live interpretation, set `OPENAI_API_KEY` and `MODEL_MODE=live` in the ignored `.env`; `OPENAI_MODEL=gpt-6.1-sol` is the tested default. The curated V2 catalog accepts only supported model IDs; arbitrary names and endpoints are rejected. In private development, if `MODEL_MODE` is omitted, a configured key selects live mode; without a key, the default is scripted. `APP_ENV=production` always starts offline and permits live access only through BYOK, regardless of private environment keys. `MODEL_MODE=scripted` never calls a model and has a deliberately limited parser. Mode is always visible. Restart the backend after configuration changes.

For frontend development, run `npm --prefix frontend run dev` alongside the backend. The Vite server proxies `/api`; use port 5173 and keep its origin in `ALLOWED_ORIGINS`.

## Model settings

Open **Model settings** from the header. Choose OpenAI, Anthropic Claude, Google Gemini, or offline mode. Every live provider selection directly presents **API key** entry for Bring Your Own Key; there is no credential-source selector. Offline Demo requires no key. The backend `.env` remains available for local development/testing, including the configured OpenAI startup default. Public production mode disables local credentials and starts offline. No frontend environment variables contain credentials.

The provider-grouped catalog offers six OpenAI IDs (GPT-6.1 Sol, GPT-6 Luna, GPT-6 Astra, GPT-5.6 Sol/Terra/Luna), four Claude IDs (Sonnet/Opus/Haiku 5.5 and Fable 5.1), and four Gemini IDs (3.8 Flash, 3.6 Flash, 3.5 Flash-Lite, 3.1 Pro Preview). Official structured-output compatibility is documented. All six OpenAI IDs were listed for the configured account; only GPT-6.1 Sol has bounded live conversational acceptance. Other models have mocked contracts and are labeled live acceptance pending; account inference access is checked by Validate & apply. GPT-6.1 Luna is omitted because the official API catalog lists GPT-6 Luna. See [current validation and remaining limits](VALIDATION.md). There is no silent provider fallback.

Enter your provider **API key** in the password field. **Validate & apply** makes one small paid structured-output call with an empty synthetic context; success starts fresh verification and clears the old conversation/summary. When a conversation exists, explicitly confirm that reset before applying. Live settings always submit BYOK, even when a local testing key exists. Current model, default model and connection-validation status remain visible. Failure keeps the current workflow. Switching is blocked during another operation; another browser tab may need a refresh before applying. The key is cleared from the input, excluded from responses/logs/model context, and encrypted with backend session state. It is never saved in browser storage or bundled frontend code. Re-enter it for revalidation. **Keep this key for new sessions in this browser** is unchecked by default. Opting in retains only the encrypted model connection across New session, subject to the existing 24-hour inactivity/cookie limit. Identity, representative role, conversation and consent always reset. Without opt-in, New session removes the key and keeps the BYOK selection visibly blocked: **Missing key — no API call** until another key is validated or Offline Demo is selected. Other connections reset to the backend default. Uncheck and apply to stop retaining the key; this uses the existing revalidation/reset flow. Session retention/backup limits still apply; use local loopback or HTTPS.

Official key setup: [OpenAI](https://platform.openai.com/api-keys), [Anthropic](https://platform.claude.com/settings/keys), [Google AI Studio](https://aistudio.google.com/apikey). Provider account access, billing and model availability can differ. Credential rejection, quota/rate limits, unavailable models, malformed output and timeouts produce safe errors without exposing provider bodies or changing SOP state. All live traffic, including BYOK and connection probes, shares the existing concurrency/rate/token budgets.

## Docker

```sh
docker compose up --build
```

Compose reads `.env`, binds only to local port 8000, and persists sessions in a named volume. Keep `DATA_DIR=/app/data` inside the container. The multi-stage build excludes `.env` and runs the backend as a nonroot user. The Linux/ARM64 image was verified on Docker Desktop, including eleven post-UAT browser checks against an isolated container and encrypted session/model-selection recovery after container recreation. That is historical evidence; current review results and Docker scope are in [VALIDATION.md](VALIDATION.md).

## Verify

```sh
.venv/bin/pytest
.venv/bin/python -m backend.evaluation --output data/policy-evaluation.json
npm --prefix frontend run build
cd frontend
npx playwright install chromium
npm run test:e2e
```

The Lab and CLI execute the same 23 isolated scripted policy scenarios. They do not use the live model or change the Playground session. Pytest uses mock interpretation and a fixed clock. Playwright starts isolated offline servers on ports 8001–8003 for the workflow, recovery and transcript suites. When targeting an external server with `CLAIMFLOW_E2E_URL`, use an isolated test instance to avoid shared session and rate-bucket interference.

Optional current conversation-relevance acceptance, **five paid API calls**, no retries:

```sh
.venv/bin/python scripts/evaluate_post_uat.py
```

It writes a sanitized report to `data/post-uat-live.json`. The historical six-call probe remains available as `scripts/evaluate_live.py`. The regular test suite never requires a key. See [validation evidence](VALIDATION.md) for the measured run and its limits.

## Important boundaries

- Before verification, no partial match counts or field results are disclosed. Three distinct approved identity fields must match one party. Policy numbers do not count. Explicit stored aliases and fixture-declared national-ID last four are allowed; conflicting details require clarification/correction.
- David's relationship is not authorization. The public representative path stays locked. The Lab's successful representative scenario supplies a clearly labeled evaluator-only identity assertion and scoped grant; the supplied consent sequences alone establish neither representative authority nor email consent.
- Claim access checks authorization on every repository read. The model cannot execute tools, set phases, approve identities, send email, or alter claims. Factual responses and summaries are rendered from supplied records/guidance.
- The January 2026 denial's recorded March 18 appeal deadline has passed. Generic timing guidance cannot override it. No late appeal, payment, document receipt, accepted substitute, or human transfer is promised.
- Summary sending is simulated, requires an explicit button, and is bound to the current preview and on-file recipient. Expiry and Skip invalidate the offer. Additional questions or case changes remove the current summary, including a previously simulated-sent summary; the next review requires fresh consent. Duplicate success returns the same simulated receipt.
- Encrypted session data and its generated private key live in `DATA_DIR` (default `data/`). Retain both across restarts; changing the encryption key invalidates old sessions. Authorization expires 15 minutes after the last authorized chat turn; server sessions expire 24 hours after the last committed mutation, and the browser cookie also lasts 24 hours; summary offers expire after 10 minutes. Private data is removed lazily on new-session creation, not by a timed deletion service.
- The backend sets HttpOnly/SameSite cookies, checks CSRF and request origins, limits input/turns/attempts, admits at most two model calls at once, and persists a daily token budget. Defaults: 40 turns/session, 120 total session mutations, 60 summary actions/client per 10 minutes, six identity-bearing attempts, 30 turns/client per 10 minutes, and 200,000 global model tokens/day with conservative reservations. Failed/uncertain model calls retain their reservation. These are demo controls, not a billing guarantee.
