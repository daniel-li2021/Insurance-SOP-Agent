# GitHub source handoff and assignment coverage

The original assignment is [`requirement.md`](../requirement.md). Keep it and all six [`insurance_claims/fixtures`](../insurance_claims/fixtures) files unchanged when transferring the implementation. Keep [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) and both dependency lockfiles.

## Download and upload

After the prepared changes are pushed, GitHub **Code → Download ZIP** on `main` downloads the tracked project. A local source ZIP is also prepared at `data/releases/ClaimFlow-source.zip` (ignored by Git). To regenerate from a reviewed commit:

```sh
mkdir -p data/releases
git archive --format=zip --prefix=ClaimFlow/ --output=data/releases/ClaimFlow-source.zip HEAD
```

`git archive` includes committed files, including `.env.example`, `.gitignore` and `.dockerignore`. It excludes `.git` history, ignored `.env` secrets, session databases/keys, `data/`, dependency folders and generated frontend assets. The Docker build regenerates assets using the checked-in lockfiles.

Unzip and upload the **contents** of `ClaimFlow/` into the original repository root, rather than uploading the ZIP or nesting the application in an extra directory. Include hidden template/ignore files; do not remove unrelated original-repository files. Preserve any original assignment/license files and resolve conflicts deliberately. For a browser upload, follow GitHub's **Add file → Upload files** flow; for a larger repository, copy the extracted contents into a local clone and commit/push there. Do not force-push or replace its history.

After transfer, confirm the repository root has `README.md`, `requirement.md`, `render.yaml`, `Dockerfile`, `compose.yaml`, `.env.example`, `requirements.lock`, `backend/`, `frontend/package-lock.json`, and the original fixtures. Use the README's local setup to smoke-test the transferred copy. Connect Render to this original repository if that is the final destination; the Blueprint has no hardcoded GitHub repository URL. No GitHub Release or second repository is created by this preparation.

## Requirement checklist

| Assignment requirement | Implementation / reviewer path |
| --- | --- |
| Hosted URL **or Docker image/repository with clear setup** | Root Dockerfile, Compose and README setup provide the repository alternative now. Render preparation is included; a public URL remains pending your manual deployment. |
| Accept an API auth token for an AI model | Model settings accepts BYOK for supported providers, with a paid validation probe. Local `.env` setup is documented in [Usage](USAGE.md). Public startup remains offline. |
| Simple natural-language test UI | React Playground with editable guided synthetic scenarios; live mode uses structured interpretation. Offline Demo is a limited parser and makes no model calls. |
| Full four-phase workflow | Standard Claim exercises identity verification, intent resolution with remembered hints, grounded claim discussion and explicit summary Send/Skip. Inspector exposes the decisions. |
| At least three distinct approved identity fields | Deterministic identity/controller gate and per-read authorization. Policy number never counts. Partial, mismatched or representative-only assertions cannot unlock claims. |
| In-scope answers, ambiguity and early memory | Controller topic/claim resolution, pending intent, clarification, out-of-scope recovery, and isolated policy replay scenarios. |
| Emotional support / SOP recovery bonus | Frustrated Caller scenario, empathetic privacy explanation, alternate identity fields and simulation-only human-assistance pause. No real transfer. |

The [architecture](ARCHITECTURE.md), [validation history](VALIDATION.md), [latest conversation polish](SMALL_POLISH.md) and [deployment preparation](DEPLOYMENT.md#preparation-validation) distinguish deterministic checks, mocked provider contracts and bounded live acceptance. The package is a synthetic prototype; summary sending and operational actions are simulated. It does not claim production insurance readiness or live acceptance for every listed model.
