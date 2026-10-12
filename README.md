# AI Code Review Bot (GitHub PR)

A full-stack FastAPI prototype for reviewing Python snippets and GitHub pull requests. The FastAPI server serves the responsive browser dashboard and API from one origin.

**Review results are advisory.** The Python analyzer uses deterministic AST rules; it does not execute submitted code. GitHub reviews use an optional AI provider when configured, or explicitly labeled demo heuristics otherwise. Findings are not verified vulnerabilities, and the app never approves, merges, or modifies a pull request.

## Features

- Responsive dashboard with code input, review progress, findings, severity filters, explanations, suggested fixes, and diff display.
- Python static analysis for selected AST patterns, plus syntax-error reporting.
- An explainable severity-count radar, a transparent record of automated checks and their limits, plus separate secure-coding reminders that are explicitly **not scanned**.
- Finding search and severity filters; affected-source context and suggested fix comparison when line/source data is available; copy controls and downloadable Markdown reports.
- Dashboard metrics and recent activity calculated from locally saved reviews, with bundled PR examples labeled as demo samples.
- GitHub pull request metadata and changed-file patches via the GitHub REST API.
- Optional OpenAI-compatible chat-completions integration, with credentials kept on the backend.
- Review history stored in local SQLite and labeled sample data for exploring the interface.
- Optional password gate using HTTP-only session cookies.
- Health checks at `/health` and `/api/health`; `/health` remains reachable for Render when access protection is enabled.

The dashboard counts use reviews saved on this service instance; bundled PR examples are demo data. Python language support is currently Python only. A clean static-analysis result only means none of the implemented rules matched. Findings do not have calibrated confidence scores. If a PR review lacks a source line or patch, the interface says so rather than inventing an affected-code excerpt.

## Requirements

- Python 3.10 or newer
- PowerShell on Windows for the commands below
- Git for version control

## Local installation and startup

Open PowerShell in the project directory:

```powershell
cd "C:\Users\ADITI VISHWAKARMA\OneDrive\Desktop\Ai code review PR"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python run.py
```

The same `python run.py` command works on Windows, Linux, macOS, and common Python hosts. It listens on `0.0.0.0` and uses the hosting platform's `PORT` environment variable, defaulting to `8000` locally. Keep that terminal open while using the server. Visit <http://127.0.0.1:8000>; API docs are at <http://127.0.0.1:8000/docs>, and the health check is <http://127.0.0.1:8000/health>. The server runs in the foreground; stopping it or closing its terminal stops the local service.

To open the app from another device on the same network, visit `http://<server-ip>:8000` and allow inbound TCP traffic to that port in the server's firewall. For a public URL, deploy the repository to a Python host such as Render; the host must provide an externally reachable URL and set `PORT`.

If PowerShell blocks virtual-environment activation, either permit it for this terminal with `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again, or run the venv executable directly:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" run.py
```

## Docker deployment

Build and start the app from the project directory:

```powershell
docker build -t ai-code-review-bot .
docker run -d --name ai-code-review-bot -p 8000:8000 --mount source=ai-code-review-bot-data,target=/app/backend/data ai-code-review-bot
```

Open <http://localhost:8000>; the health check is at <http://localhost:8000/health>. Review history is stored in the named `ai-code-review-bot-data` volume and survives container replacement. To configure GitHub, an AI provider, or access protection, create `.env` from `.env.example` and add `--env-file .env` to the `docker run` command. Keep `.env` out of source control.

To stop and remove the container while keeping review history, run `docker stop ai-code-review-bot` and `docker rm ai-code-review-bot`. To remove the saved history as well, remove the volume with `docker volume rm ai-code-review-bot-data`.

## Tests

With the virtual environment active:

```powershell
python -m pytest backend\tests -q
```

## Configuration

Copy `.env.example` to `.env`. The local app loads that file at startup. Restart the server after changing values.

| Variable | Purpose |
| --- | --- |
| `GITHUB_TOKEN` | Optional GitHub token for private repositories or higher API limits. Grant only read access to the repositories and pull requests being reviewed. |
| `LLM_API_KEY` | Optional key for an OpenAI-compatible chat-completions provider. Leave empty to use labeled demo heuristics on live PR diffs. |
| `LLM_BASE_URL` | Provider API base URL; defaults to `https://api.openai.com/v1`. |
| `LLM_MODEL` | Provider model name; defaults to `gpt-4o-mini`. |
| `CODE_SENTINEL_USERNAME` / `CODE_SENTINEL_PASSWORD` | Set both to enable the optional access-protection screen. Setting only one makes the service return an error instead of disabling protection. |
| `CORS_ORIGINS` | Comma-separated allowed browser origins when serving the UI separately. The bundled UI is same-origin and does not need CORS. |
| `HOST` / `PORT` | Defaults to `0.0.0.0:8000`; hosting platforms can override `PORT` with their assigned listening port. |

Never put credentials in `frontend/`, source control, or a public issue. `.env` is ignored by Git. On Render, configure secrets in the service's Environment settings rather than adding them to `render.yaml`. Without the optional password gate, anyone who can reach the deployed service can submit code for analysis and view its history.

### GitHub pull requests

Select **GitHub PR**, enter a repository URL such as `https://github.com/owner/repository` and a pull request number. Public PRs work without a token, subject to GitHub's anonymous rate limit. For private repositories, configure `GITHUB_TOKEN` with read-only access. Missing repositories/permissions and rate limits are returned as API errors. GitHub may omit patches for binary or large files; the API exposes at most 3,000 changed files for one PR.

### AI provider

Set `LLM_API_KEY`, and optionally `LLM_BASE_URL` and `LLM_MODEL`. The server sends the retrieved PR diff to that provider; review its privacy and retention policy before enabling this integration. Code-snippet reviews use the built-in Python AST analyzer and do not call the AI provider.

## Render deployment

The included [`render.yaml`](./render.yaml) builds the app from the [`Dockerfile`](./Dockerfile), deploys the container on Render's free Singapore region, and uses `/health` for its health check. The container starts `run.py`, which binds to `0.0.0.0` and uses the host-provided `PORT`. The root [`Procfile`](./Procfile) provides the same startup command to hosts that use Procfiles.

1. Push this project to a GitHub repository you own (see below).
2. Sign in to Render and choose **New + → Blueprint**.
3. Connect that repository and deploy the blueprint. Render reads `render.yaml` and creates the web service.
4. If needed, open the service's **Environment** page and configure `GITHUB_TOKEN`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and both access-protection values there. Do not commit secret values.
5. Wait for the deploy and `/health` check to succeed. Render displays the public `https://<service-name>.onrender.com` URL in the service dashboard.

The service writes SQLite review history under `backend/data/`. On Render instances without a persistent disk, this local history may be lost when the instance is replaced or redeployed. The current prototype does not configure a persistent database.

Render's free web services may spin down after a period of inactivity; the first request after spin-down can take longer while the service starts. Availability, spin-down behavior, and plan limits depend on Render's current plan. An external LLM API is optional, but using a paid AI provider generally requires your own provider account, API key, and billing; those charges are separate from Render hosting. The built-in Python AST checks and GitHub public-PR retrieval do not require an LLM API key.

## Upload this project to your own GitHub repository

The project folder may be inside a larger parent Git repository. Initialize Git **from this project directory** so that only this project is the repository, and verify the root before staging:

```powershell
cd "C:\Users\ADITI VISHWAKARMA\OneDrive\Desktop\Ai code review PR"
git init
git rev-parse --show-toplevel
git status --short
```

The reported root should be the `Ai code review PR` directory. Check that `.env`, `.venv`, caches, and SQLite files are ignored before adding files:

```powershell
git check-ignore .env .venv backend\data\review_history.sqlite3
git add .
git status --short
git commit -m "Build AI code review bot prototype"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Create an empty repository on GitHub first and replace the remote URL with your own. Do not continue if `git rev-parse --show-toplevel` reports a parent directory: that would risk adding unrelated files. Inspect `git status --short` before committing.

## Troubleshooting

 - **`ModuleNotFoundError` when starting:** activate the project's `.venv` and install `python -m pip install -r requirements.txt` from the project directory.
- **The browser cannot connect:** keep Uvicorn running, use the URL printed by Uvicorn (local default is port 8000), and check `/health`.
- **GitHub 404/403/429:** check the repository/PR URL, token permissions and repository access, or wait for the rate limit to reset.
- **AI provider error:** verify the backend environment key, provider base URL, model name, and provider quota. Without `LLM_API_KEY`, live PR analysis uses demo heuristics and is labeled accordingly.

## Project structure

```text
backend/
  data/                 Bundled sample data and local review history
  services/             Python analysis, GitHub, AI, demo, and history logic
  tests/                API and analysis tests
  main.py               FastAPI application
  schemas.py            Request and response models
run.py                    Cross-platform entry point (uses host-provided PORT)
Procfile                  Generic Python-host startup command
frontend/                 Static browser interface
.env.example             Safe configuration template
render.yaml              Render web-service configuration
Dockerfile               Docker image and container startup configuration
.dockerignore             Files excluded from the Docker build context
requirements.txt         Python dependencies
```
