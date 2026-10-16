# ClaimFlow — Insurance SOP Agent

A working insurance support demo: natural language interpretation, deterministic SOP enforcement, authorized fixture access, a chat playground with a decision inspector, and a replayable Evaluation Lab.

`VERIFY_ID → RESOLVE_INTENT → PROCESS_CASE → POST_PROCESS`

![ClaimFlow summary and workflow inspector in offline mode](docs/screenshots/final-summary-desktop.png)

Final acceptance: **96 backend tests, 23 policy scenarios, 11 Docker browser tests, and production frontend build passed**. See the [requirement-by-requirement review and UI acceptance](docs/FINAL_VALIDATION.md).

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

For live interpretation, set `OPENAI_API_KEY` and `MODEL_MODE=live` in the ignored `.env`; `OPENAI_MODEL=gpt-6.1-sol` is the tested default. The curated V2 catalog accepts only supported model IDs; arbitrary names and endpoints are rejected. If `MODEL_MODE` is omitted, a configured key selects live mode; without a key, the default is scripted. `MODEL_MODE=scripted` never calls a model and has a deliberately limited parser. Mode is always visible. Restart the backend after configuration changes.

For frontend development, run `npm --prefix frontend run dev` alongside the backend. The Vite server proxies `/api`; use port 5173 and keep its origin in `ALLOWED_ORIGINS`.

## Model settings (V2)

Open **Model settings** from the header. Choose OpenAI, Anthropic Claude, Google Gemini, or offline mode. The existing backend OpenAI key/model remains the local default. Optional `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` environment variables make demo credentials available for those providers. No frontend environment variables contain credentials.

The catalog is intentionally small: `gpt-6.1-sol`, `claude-sonnet-5-5`, and `gemini-3.8-flash`. OpenAI has live acceptance evidence. Claude/Gemini have mocked contract evidence and require live validation with your provider account; the dialog labels that distinction. There is no silent provider fallback.

Choose **Bring Your Own Key** to enter a provider key in the password field. **Validate & apply** makes one small paid structured-output call with an empty synthetic context; success starts fresh verification and clears the old conversation/summary. When a conversation exists, explicitly confirm that reset before applying. If a demo key is unavailable, **Use my own key** opens BYOK directly. Failure keeps the current workflow. Switching is blocked during another operation; another browser tab may need a refresh before applying. The key is cleared from the input, excluded from responses/logs/model context, and encrypted with backend session state. It is never saved in browser storage or bundled frontend code. Re-enter it for revalidation. **New session** removes the session row/key and returns to the backend default. Session retention/backup limits still apply; use local loopback or HTTPS.

Official key setup: [OpenAI](https://platform.openai.com/api-keys), [Anthropic](https://platform.claude.com/settings/keys), [Google AI Studio](https://aistudio.google.com/apikey). Provider account access, billing and model availability can differ. Credential rejection, quota/rate limits, unavailable models, malformed output and timeouts produce safe errors without exposing provider bodies or changing SOP state. All live traffic, including BYOK and connection probes, shares the existing concurrency/rate/token budgets.

## Docker

```sh
docker compose up --build
```

Compose reads `.env`, binds only to local port 8000, and persists sessions in a named volume. Keep `DATA_DIR=/app/data` inside the container. The multi-stage build excludes `.env` and runs the backend as a nonroot user. The Linux/ARM64 image and Compose runtime were verified on Docker Desktop, including eleven final browser checks and encrypted session/model-selection recovery after container recreation. See [final acceptance evidence](docs/FINAL_VALIDATION.md).

## Verify

```sh
.venv/bin/pytest
.venv/bin/python -m backend.evaluation --output data/policy-evaluation.json
npm --prefix frontend run build
cd frontend
npx playwright install chromium
npm run test:e2e
```

The Lab and CLI execute the same 23 isolated scripted policy scenarios. They do not use the live model or change the Playground session. Pytest uses mock interpretation and a fixed clock. Playwright starts its own offline server on port 8001.

Optional live-model acceptance probe, **six paid API calls**:

```sh
.venv/bin/python scripts/evaluate_live.py
```

It writes a sanitized report to `data/live-evaluation.json`. The regular test suite never requires a key. See [validation evidence](docs/VALIDATION.md) for the measured run and its limits.

## Important boundaries

- Before verification, no partial match counts or field results are disclosed. Three distinct approved identity fields must match one party. Policy numbers do not count. Explicit stored aliases and fixture-declared national-ID last four are allowed; conflicting details require clarification/correction.
- David's relationship is not authorization. The public representative path stays locked. The Lab's successful representative scenario supplies a clearly labeled evaluator-only identity assertion and scoped grant; the supplied consent sequences alone establish neither representative authority nor email consent.
- Claim access checks authorization on every repository read. The model cannot execute tools, set phases, approve identities, send email, or alter claims. Factual responses and summaries are rendered from supplied records/guidance.
- The January 2026 denial's recorded March 18 appeal deadline has passed. Generic timing guidance cannot override it. No late appeal, payment, document receipt, accepted substitute, or human transfer is promised.
- Summary sending is simulated, requires an explicit button, and is bound to the current preview and on-file recipient. Expiry and Skip invalidate the offer. Additional questions or case changes remove the current summary, including a previously simulated-sent summary; the next review requires fresh consent. Duplicate success returns the same simulated receipt.
- Encrypted session data and its generated private key live in `DATA_DIR` (default `data/`). Retain both across restarts; changing the encryption key invalidates old sessions. Authorization expires 15 minutes after the last authorized chat turn; server sessions expire 24 hours after the last committed mutation, and the browser cookie also lasts 24 hours; summary offers expire after 10 minutes. Private data is removed lazily on new-session creation, not by a timed deletion service.
- The backend sets HttpOnly/SameSite cookies, checks CSRF and request origins, limits input/turns/attempts, admits at most two model calls at once, and persists a daily token budget. Defaults: 40 turns/session, 120 total session mutations, 60 summary actions/client per 10 minutes, six identity-bearing attempts, 30 turns/client per 10 minutes, and 200,000 global model tokens/day with conservative reservations. Failed/uncertain model calls retain their reservation. These are demo controls, not a billing guarantee.

## Hosting

Prefer one paid Render Docker service with a persistent disk mounted at `/app/data`. Set `APP_ENV=production`, exact HTTPS `ALLOWED_ORIGINS`, model token/model, and budget in backend environment settings. A generated encryption key remains on that disk, or supply a stable Fernet `SESSION_ENCRYPTION_KEY`. Do not expose secrets to frontend builds. Public hosting has not been provisioned.

The disk limits the service to one instance and causes brief deployment downtime. Use SQLite's backup API for consistent backups. The default server does not trust forwarded client-IP headers: users behind a proxy can share a conservative rate bucket. Verify proxy configuration before changing that boundary. Render Free's ephemeral storage and idle sleep do not meet durable-session expectations. See [deployment trade-offs](docs/PROPOSAL.md#7-deployment-recommendation).

## Further reading and limitations

- [Independent reliability, security, and workflow review](docs/RELIABILITY_REVIEW.md)
- [Implementation architecture and security boundaries](docs/ARCHITECTURE.md)
- [Open-source research and reuse decisions](docs/REUSE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Accepted proposal](docs/PROPOSAL.md) · [Original assignment](requirement.md) · [Six unchanged fixtures](insurance_claims/fixtures)

This is synthetic static-data authentication, not production healthcare identity assurance. There are no real uploads, appeals, payments, transfers, or email deliveries. Scripted mode is limited; grounded factual phrasing is intentionally controlled. Small live-model probes do not establish general conversational quality. Production authentication, insurer-approved representative proof and policy rules, real integrations, operational availability, and appropriate provider data-handling arrangements require separate work.

The [12-call V1 acceptance closure](docs/VALIDATION.md#v1-live-acceptance-closure--october-16-2026) validates the core journey and emotional-support/SOP-recovery bonus within the bounded synthetic demo scope. Repeat only when relevant behavior changes: `.venv/bin/python scripts/evaluate_v1_acceptance.py` (12 paid calls, no automatic retries).
