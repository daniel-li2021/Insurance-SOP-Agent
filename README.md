# ClaimFlow — Insurance SOP Agent

A working insurance support demo: natural language interpretation, deterministic SOP enforcement, authorized fixture access, a chat playground with a decision inspector, and a replayable Evaluation Lab.

`VERIFY_ID → RESOLVE_INTENT → PROCESS_CASE → POST_PROCESS`

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

Open [localhost:8000](http://localhost:8000). Choose **Try a guided scenario** to insert Margaret's supplied synthetic opening, or type a conversation. Review the summary to explicitly Send a simulation or Skip. No real email is delivered.

For live interpretation, set `OPENAI_API_KEY` and `MODEL_MODE=live` in the ignored `.env`; `OPENAI_MODEL=gpt-6.1-sol` is the tested default. `gpt-6-luna` is configurable, but was not evaluated here. If `MODEL_MODE` is omitted, a configured key selects live mode; without a key, the default is scripted. `MODEL_MODE=scripted` never calls a model and has a deliberately limited parser. Mode is always visible. Restart the backend after configuration changes.

For frontend development, run `npm --prefix frontend run dev` alongside the backend. The Vite server proxies `/api`; use port 5173 and keep its origin in `ALLOWED_ORIGINS`.

## Docker

```sh
docker compose up --build
```

Compose reads `.env`, binds only to local port 8000, and persists sessions in a named volume. Keep `DATA_DIR=/app/data` inside the container. The multi-stage build excludes `.env` and runs the backend as a nonroot user. Docker is not installed in the development environment, so image execution has not been verified.

## Verify

```sh
.venv/bin/pytest
.venv/bin/python -m backend.evaluation --output data/policy-evaluation.json
npm --prefix frontend run build
cd frontend
npx playwright install chromium
npm run test:e2e
```

The Lab and CLI execute the same 19 isolated scripted policy scenarios. They do not use the live model or change the Playground session. Pytest uses mock interpretation and a fixed clock. Playwright starts its own offline server on port 8001.

Optional live-model acceptance probe, **six paid API calls**:

```sh
.venv/bin/python scripts/evaluate_live.py
```

It writes a sanitized report to `data/live-evaluation.json`. The regular test suite never requires a key. See [validation evidence](docs/VALIDATION.md) for the measured run and its limits.

## Important boundaries

- Three distinct approved identity fields must match one party. Policy numbers do not count. Explicit stored aliases and fixture-declared national-ID last four are allowed; conflicting details require clarification/correction.
- David's relationship is not authorization. The public representative path stays locked. The Lab's successful representative scenario supplies a clearly labeled evaluator-only identity assertion and scoped grant; the supplied consent sequences alone establish neither representative authority nor email consent.
- Claim access checks authorization on every repository read. The model cannot execute tools, set phases, approve identities, send email, or alter claims. Factual responses and summaries are rendered from supplied records/guidance.
- The January 2026 denial's recorded March 18 appeal deadline has passed. Generic timing guidance cannot override it. No late appeal, payment, document receipt, accepted substitute, or human transfer is promised.
- Summary sending is simulated, requires an explicit button, and is bound to the current preview and on-file recipient. Expiry, Skip, and additional questions invalidate the offer. Duplicate success returns the same simulated receipt.
- Encrypted session data and its generated private key live in `DATA_DIR` (default `data/`). Retain both across restarts; changing the encryption key invalidates old sessions. Authorization expires after 15 idle minutes; sessions expire after 24 idle hours; summary offers expire after 10 minutes. Private data is removed lazily on new-session creation, not by a timed deletion service.
- The backend sets HttpOnly/SameSite cookies, checks CSRF and request origins, limits input/turns/attempts, admits at most two model calls at once, and persists a daily token budget. Defaults: 40 turns/session, 120 total session mutations, 60 summary actions/client per 10 minutes, six identity-bearing attempts, 30 turns/client per 10 minutes, and 200,000 global model tokens/day with conservative reservations. Failed/uncertain model calls retain their reservation. These are demo controls, not a billing guarantee.

## Hosting

Prefer one paid Render Docker service with a persistent disk mounted at `/app/data`. Set `APP_ENV=production`, exact HTTPS `ALLOWED_ORIGINS`, model token/model, and budget in backend environment settings. A generated encryption key remains on that disk, or supply a stable Fernet `SESSION_ENCRYPTION_KEY`. Do not expose secrets to frontend builds. Public hosting has not been provisioned.

The disk limits the service to one instance and causes brief deployment downtime. Use SQLite's backup API for consistent backups. The default server does not trust forwarded client-IP headers: users behind a proxy can share a conservative rate bucket. Verify proxy configuration before changing that boundary. Render Free's ephemeral storage and idle sleep do not meet durable-session expectations. See [deployment trade-offs](docs/PROPOSAL.md#7-deployment-recommendation).

## Further reading and limitations

- [Implementation architecture and security boundaries](docs/ARCHITECTURE.md)
- [Open-source research and reuse decisions](docs/REUSE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Accepted proposal](docs/PROPOSAL.md) · [Original assignment](requirement.md) · [Six unchanged fixtures](insurance_claims/fixtures)

This is synthetic static-data authentication, not production healthcare identity assurance. There are no real uploads, appeals, payments, transfers, or email deliveries. Scripted mode is limited; grounded factual phrasing is intentionally controlled. Small live-model probes do not establish general conversational quality. Production authentication, insurer-approved representative proof and policy rules, real integrations, operational availability, and appropriate provider data-handling arrangements require separate work.
