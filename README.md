# ClaimFlow — Insurance SOP Agent

An insurance support demo that combines natural-language interpretation with a deterministic business workflow. Explore a fictional claim, inspect the decisions behind each answer, and review an email summary with explicit Send or Skip consent.

**[Try the live demo](https://claimflow-demo.onrender.com/)** · Starts offline; no API key needed for guided scenarios.

`VERIFY_ID → RESOLVE_INTENT → PROCESS_CASE → POST_PROCESS`

![ClaimFlow discussion summary using synthetic records](docs/screenshots/post-uat-summary.png)

## What it demonstrates

- **Strict identity gates:** three distinct approved identity fields must match one fictional policyholder before claim access. Early intent is remembered while verification continues.
- **Grounded claim support:** resolve ambiguous claims, explain recorded outcomes, discuss document alternatives, and handle frustration without bypassing the SOP.
- **Visible decisions:** the Workflow Inspector shows phases and source evidence. The Evaluation Lab replays 23 isolated scripted policy scenarios without model calls.
- **Explicit follow-up:** preview a summary, then Send a simulation or Skip. No real email, appeal, payment, upload or human transfer occurs.

One FastAPI service serves the React/Vite UI and API, with encrypted SQLite sessions. The model proposes structured interpretations; Python controls authorization, record access, workflow transitions and consent. See [architecture](docs/ARCHITECTURE.md).

## Run locally

With Docker installed:

```sh
cp -n .env.example .env
docker compose up --build
```

Open [localhost:8000](http://localhost:8000). The default **Offline Demo** works without an API key. Select **Try a guided scenario → Standard Claim**, use its synthetic opening, and send it. Ask about required documents or recorded payments, then review the summary and choose Send or Skip. Try Frustrated Caller or Ambiguous Claim to inspect the safety gates.

For live natural-language interpretation, open **Model settings**, choose a provider/model, enter your own API key, and select **Validate & apply**. Validation makes one small paid call and resets the conversation after confirmation. Live turns use that key and incur provider charges. Keys are kept server-side in encrypted session state; use fictional details only. Offline parsing is deliberately limited.

Python 3.11+ and Node 22 setup, frontend development, key retention and detailed controls are in the [usage guide](docs/USAGE.md).

## Render demo

The repository includes a [Render Blueprint](render.yaml) for one Docker web service with a 1 GB persistent disk. It starts offline, disables owner environment keys in public mode, uses secure session cookies, and disables automatic deploys. **The configured compute and disk are paid resources; review the dashboard price before creating them.**

The [public demo](https://claimflow-demo.onrender.com/) is live. A short HTTPS/offline smoke check passed on October 17, 2026: UI/assets, health, session security, synthetic identity verification and summary preview. This is a bounded smoke check, not an availability or load guarantee. See the [manual Render guide](docs/DEPLOYMENT.md) for setup and future releases; automatic deploys are disabled in the Blueprint.

## Verify and hand off

```sh
.venv/bin/pytest tests/test_deployment.py tests/test_api.py tests/test_settings.py
npm --prefix frontend run build
```

Install local dependencies first using the [usage guide](docs/USAGE.md). Historical model and browser acceptance is recorded in [validation evidence](docs/VALIDATION.md); the [deployment guide](docs/DEPLOYMENT.md#preparation-validation) records checks for this preparation. Small synthetic probes do not establish general model reliability.

To download the source and upload it to the original assignment repository, follow the [GitHub handoff and requirement checklist](docs/HANDOFF.md). The Docker repository with setup instructions satisfies the assignment's delivery alternative; the hosted demo is also available at the link above.

## Scope and documentation

This is a portfolio prototype using six supplied synthetic fixtures, not production identity assurance or an insurer integration. Representative relationships do not grant access; the successful representative flow exists only in the isolated evaluator. Expired recorded deadlines remain expired. Live provider/model acceptance varies; see the validation reports.

- [Usage, model settings and operational limits](docs/USAGE.md)
- [Render setup, security profile and post-deploy checks](docs/DEPLOYMENT.md)
- [GitHub handoff and assignment coverage](docs/HANDOFF.md)
- [Architecture](docs/ARCHITECTURE.md) · [Validation history](docs/VALIDATION.md)
- [Original assignment](requirement.md) · [Original fixtures](insurance_claims/fixtures)
- [Reuse decisions](docs/REUSE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
