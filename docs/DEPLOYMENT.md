# Manual Render deployment

Status: **[public demo live](https://claimflow-demo.onrender.com/)**, deployed manually by the owner. The initial preparation baseline was GitHub `main` at `b5bc3e9`; that preparation created no Render resources.

A short public smoke check on October 17, 2026 passed trusted HTTPS, the UI and two hashed assets, offline health (`328f5c17f69b` fixtures), Secure/HttpOnly/SameSite cookies, CSRF and foreign-origin rejection, disabled owner credentials, hidden docs/schema/private-file paths, synthetic identity verification and summary preview. No paid model calls or Render configuration changes were made. The owner requested no further inspection; public restart persistence, disk configuration, live providers, load and availability were not checked. Subsequent source changes, including the review fixes in [VALIDATION.md](VALIDATION.md), require owner review, integration and a manual Render deploy to appear publicly. This review did not inspect or change the public service.

## Hosting profile

[`render.yaml`](../render.yaml) defines one Docker web service, `claimflow-demo`, on `main` in Oregon, using the paid `0.5c-512mb` compute plan and a 1 GB persistent disk at `/app/data`. Review current compute and disk charges in Render before applying it. No external database, worker or static-site service is needed. Choose a unique service name if the dashboard requires one.

The existing multi-stage Dockerfile builds the UI with Node 22 and installs locked Python dependencies. It serves UI and API from one origin, runs as UID 10001, binds `0.0.0.0:$PORT`, defaults locally to port 8000, and keeps one Uvicorn worker. Health check: `/api/health`. The process uses `--no-proxy-headers`: arbitrary forwarded IP headers cannot bypass limits; proxy users can share a conservative rate bucket.

The disk stores the encrypted SQLite database, encryption key, rate buckets and daily token ledger together. Preserve it across deploys. Render Free cannot attach this disk, and ephemeral storage loses sessions and resets budgets; it is unsuitable for this profile. A disk-backed service has one instance and brief deployment downtime. Do not add workers or instances to work around that restriction.

## Deploy manually after review

1. Push the reviewed files to `main` in the GitHub repository you intend to deploy. Confirm the root contains `render.yaml`, `Dockerfile`, both dependency lockfiles, `backend/`, `frontend/` and the fixtures.
2. In the [Render Dashboard](https://dashboard.render.com), connect GitHub with access to that repository. Choose **New → Blueprint**, select the repository and `main`, and review `render.yaml`.
3. Confirm one paid web service and one 1 GB disk, the branch, region and pricing. Review the environment settings below. No owner API key is required.
4. **Stop here until you intend to deploy.** Clicking the final create/apply control starts the initial build and deployment. `autoDeployTrigger: off` prevents subsequent Git pushes from automatically deploying; it does not suppress the first deployment. Keep any dashboard Blueprint auto-sync setting manual as well if you want to review infrastructure changes before applying them.
5. When ready, apply it yourself. Wait for Render's deploy to become live, then run the checks below. Future releases use the dashboard's manual deploy control; review Blueprint configuration changes before syncing them.

Alternatively, **New → Web Service → Git Provider** can use the same repository. Select Docker, `main`, repository root, Dockerfile `./Dockerfile`, the same paid plan/region, one instance, health path `/api/health`, automatic deploys Off, and a 1 GB disk mounted at `/app/data`. Add the four environment values below **before** creating the service. Leave the Docker command override empty to use the image's CMD. Choose either this route or Blueprint creation; doing both creates duplicate services.

## Environment and security

| Variable | Prepared value / behavior |
| --- | --- |
| `APP_ENV` | `production`: Secure/HttpOnly/SameSite session cookie, hidden API docs/schema, offline default and local provider credentials disabled. |
| `MODEL_MODE` | `scripted`: no startup model calls. Visitors can explicitly validate their own key in Model settings. |
| `DATA_DIR` | `/app/data`, matching the persistent disk. |
| `DAILY_TOKEN_LIMIT` | `200000`: shared across all visitor keys, probes and live turns; lower it if desired. |
| `ALLOWED_ORIGINS` | Omit on Render to use its trusted `RENDER_EXTERNAL_URL`. For a custom domain, set a comma-separated list of exact HTTPS origins, e.g. `https://demo.example.com,https://your-service.onrender.com`. An explicit list replaces the default. Paths, wildcards, credentials and HTTP origins are rejected at startup. |
| `SESSION_ENCRYPTION_KEY` | Omit to generate a private Fernet key on the persistent disk. If supplied separately, use a stable valid Fernet key and retain it with database backups. Rotation makes old sessions unreadable. |

Do not copy the development `.env` into Render or an image. In particular, its localhost origin list is for local development. Leave `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` absent; public production mode ignores those credentials even if accidentally configured. Never use frontend environment variables for keys. `RENDER_EXTERNAL_URL` and `PORT` are supplied by Render; do not derive origin trust from request headers.

Visitors start in Offline Demo. Live use requires explicit BYOK validation, which makes one paid probe. Keys are sent to this backend and held in encrypted server session state; they are not browser-only secrets. New-session retention is opt-in, and encrypted backups can retain historical payloads. Use this hosted app only for synthetic records, and use local mode if you prefer not to give a hosted service your key. The UI already labels synthetic data and simulated delivery.

Existing controls include request-size/CSRF/origin checks, two concurrent model calls, per-client operation limits, per-session turn/identity-attempt limits, no provider retries, 30-second call deadlines, and durable daily token reservations. Failed or uncertain calls keep reservations. These are bounded demo controls, not a dollar spending guarantee or comprehensive abuse protection. New sessions are intentionally uncapped; monitor disk growth and traffic, and suspend the demo if abused. Sessions expire after 24 hours of inactivity and are removed lazily on new-session creation, not by a scheduled deletion service. Do not enable request-body/debug logging when handling visitor keys.

## Checks after you deploy

- Open the HTTPS URL. Confirm the UI loads, displays Offline/Scripted, and offers guided scenarios. `/api/health` should return `status: ok`, `mode: scripted`, `model: scripted` and a fixture version. This is a process/fixture check; it does not validate live provider access or disk capacity.
- Run Standard Claim using synthetic details: verification → denied January claim → document/payment follow-up → summary → Send simulation or Skip. Check the Workflow Inspector and one scripted Evaluation Lab replay.
- Confirm `/api/docs`, `/openapi.json`, `/.env`, `/data/sessions.sqlite3` and `/docs/fixtures/claims.json` return 404. Confirm session cookies have Secure, HttpOnly and SameSite=Strict and cross-origin mutations fail.
- Refresh the page; then manually restart/redeploy and confirm the committed session returns. Verify `/app/data` is writable by the container user and retained; do not delete the disk to fix permissions. If live testing is desired, use your own limited key and expect a paid probe/turn; no live call is needed for the offline smoke.
- Once verified, add the actual HTTPS demo URL near the top of the README. Do not publish an invented or pending URL as live.

If startup fails: inspect Render logs for invalid HTTPS origins, a malformed encryption key, unwritable `/app/data` or a missing frontend build. Check the disk mount and environment before changing application security. Do not enable wildcard origins, trust all proxy headers, switch to multiple workers, or disable Secure cookies as a workaround.

For backups, use SQLite's online backup API and preserve the matching encryption key securely. Do not treat a filesystem snapshot as proof of a consistent running SQLite backup. Keep backups, visitor state and keys outside Git/source packages.

## Validation scope

The original deployment preparation used baseline `b5bc3e9` and passed 63 focused backend cases, a Linux/ARM64 Docker build, three Chromium journeys against a local HTTPS production-profile container, HTTP security checks and persisted session/budget restart checks. A later short public offline smoke check is described above. Those are historical runs; the owner-managed public service was not inspected during the current review.

Current source acceptance, exact test counts, review findings, final image identity and remaining limits are maintained in [VALIDATION.md](VALIDATION.md). Review that report before integrating and manually releasing this branch. Local Docker evidence does not establish hosted availability, public persistence or live provider quality.

## Platform references

Checked October 17, 2026: [Blueprint specification](https://render.com/docs/blueprint-spec), [compute plans](https://render.com/docs/compute-plans), [web services and port binding](https://render.com/docs/web-services), [persistent disks](https://render.com/docs/disks), [environment variables](https://render.com/docs/configure-environment-variables), and [Render-provided variables](https://render.com/docs/environment-variables). Blueprint/schema validation is read-only and does not create or deploy resources.
