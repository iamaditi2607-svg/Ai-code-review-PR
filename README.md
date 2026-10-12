# AI-Powered GitHub Code Review & Debugging Assistant

A lightweight, auditable prototype for reviewing Python code snippets and GitHub pull request diffs.

Tagline: Practical, explainable static analysis with an optional AI-assisted review path (developer opt-in).

Project description

This repository contains a full-stack prototype that provides an interactive browser dashboard and a FastAPI backend to run explainable Python static analysis, display results, save review history locally, and optionally forward diffs to an OpenAI-compatible provider when configured. The system is intended as a developer tool and research prototype — not a production security scanner.

Live demo

- https://ai-code-review-bot-77vs.onrender.com/ (deployed instance)

What this project solves

Many teams need quick, explainable feedback on Python code changes and PR diffs without running full CI pipelines. This project provides:

- Fast, deterministic AST-based checks for common patterns and issues in Python snippets and changed files.
- A simple UI to explore findings, suggested fixes, and download reports.
- A reproducible local review history for metrics and demo purposes.

Important: implemented vs. planned features

Implemented and tested (based on repository source code):

- Responsive static frontend served from frontend/ (index.html, app.js, style.css).
- FastAPI backend (backend/main.py) that exposes review APIs and health endpoints.
- Deterministic Python static analysis using AST patterns (no code execution).
- Local SQLite-backed review history under backend/data/ (used for dashboard metrics).
- Optional integration points for an OpenAI-compatible LLM provider (controlled via environment variables). When LLM credentials are not provided the app uses labeled demo heuristics; the LLM path is opt-in and requires real credentials to operate.
- Ability to fetch GitHub PR metadata and patch data via the GitHub REST API (requires GITHUB_TOKEN for private repos or higher rate limits).
- Password-based optional access gate using CODE_SENTINEL_USERNAME / CODE_SENTINEL_PASSWORD.

Planned / not implemented here (do not claim these are available unless you add code):

- Fully automated PR reviews that merge, label, or modify PRs on GitHub.
- Unsupervised vulnerability scanning or automated fix application.
- Any functionality that requires executing analyzed code.

Technology stack (based on repository files)

- Language: Python 3.10+
- Web framework: FastAPI
- ASGI server: Uvicorn (run.py starts the app)
- Persistence: SQLite (backend/data/)
- Frontend: Static HTML/CSS/JavaScript (frontend/index.html, frontend/app.js)
- Deployment: Docker (Dockerfile), Render (render.yaml)
- Optional: OpenAI-compatible LLM provider via REST (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL)

Architecture and workflow

- frontend/ — static single-page interface that calls the backend API endpoints.
- backend/main.py — FastAPI application that exposes endpoints for creating reviews, fetching history, health checks, and optionally proxying requests to an LLM provider.
- backend/services/ — analysis, GitHub integration, demo heuristics, and history persistence (refer to source for details).
- backend/data/ — bundled sample data and the SQLite review history file.
- run.py — cross-platform entry point used for local runs and many hosting services.

High-level workflow:

1. User opens the dashboard and submits a code snippet or a GitHub PR URL + PR number.
2. The backend fetches PR metadata and patch data (if a PR was provided).
3. Deterministic AST-based analyzers run against the changed Python files or submitted snippet and produce findings.
4. Findings are returned to the frontend for display; the review may be saved to the local SQLite history.
5. If configured, the backend can forward the PR diff to an OpenAI-compatible provider and include that provider's response in the review (developer opt-in — requires LLM_API_KEY).

Security and limitations

- The analyzer is purely static and deterministic: it uses AST pattern matching and does not execute submitted or repository code.
- The optional LLM integration sends PR diffs to the configured provider — do not enable it for private or sensitive code without reviewing the provider's data handling policy.
- This prototype is NOT a replacement for formal security scanners or CI-based checks. Use it for fast, explainable heuristics and education.

Screenshots

- There are no images checked into this repo. If you have screenshots of the running UI, add them to docs/images/ or the repository root and update this README to reference them. Example markdown to add after you upload images:

  ![Dashboard screenshot](docs/images/dashboard.png)

Local installation and setup

Prerequisites

- Python 3.10 or newer
- Git
- (Optional) Docker

Clone and run (recommended cross-platform steps)

```bash
git clone https://github.com/iamaditi2607-svg/Ai-code-review-PR.git
cd Ai-code-review-PR
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
# .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env as needed; see placeholders below
python run.py
```

The server listens on the port defined by the PORT environment variable (default 8000). Open http://localhost:8000/ in your browser.

Docker (build + run)

```bash
docker build -t ai-code-review-bot .
docker run -d --name ai-code-review-bot -p 8000:8000 --mount source=ai-code-review-bot-data,target=/app/backend/data ai-code-review-bot
```

Running tests

Tests live under backend/tests/. To run them locally:

```bash
python -m pytest backend/tests -q
```

Configuration / required environment variables

Copy .env.example to .env and edit only the placeholders. Never commit secrets.

Example placeholders (do not put real secrets here):

- GITHUB_TOKEN=YOUR_GITHUB_TOKEN_HERE
- LLM_API_KEY=YOUR_LLM_API_KEY_HERE
- LLM_BASE_URL=https://api.openai.com/v1
- LLM_MODEL=gpt-4o-mini
- CODE_SENTINEL_USERNAME=youruser
- CODE_SENTINEL_PASSWORD=yourpassword
- HOST=0.0.0.0
- PORT=8000

What I changed in this repository

- Polished and reorganized README.md to use the professional project title and to clearly distinguish implemented vs planned features. (This file was updated in-place.)

Files changed by this commit

- README.md

How you can review and commit these changes locally

1. Fetch the latest repository and inspect the README:

```bash
git pull origin main
git show HEAD:README.md | sed -n '1,120p'
```

2. If you want to edit further locally, modify README.md, then run:

```bash
git add README.md
git commit -m "docs: polish README and project branding"
git push
```

Profile README suggestion (for your GitHub profile repository)

Create a repository named exactly: iamaditi2607-svg (this is the special profile repository). Add a README.md with the content below (customize it):

---
# Aditi Vishwakarma (iamaditi2607-svg)

Developer focused on Python, web APIs, and building developer tooling. I enjoy exploring explainable AI, static analysis, and developer experience improvements.

Pinned projects

1) AI-Powered GitHub Code Review & Debugging Assistant
- Repo: https://github.com/iamaditi2607-svg/Ai-code-review-PR
- Stack: Python, FastAPI, SQLite, Vanilla JS, Docker
- Status: Prototype — working demo deployed; optional LLM integrations require configuration.

2) [Add your second project here]
- Repository: (add repo link)
- Stack: (languages / frameworks)
- Status: (in-progress / complete)

Skills & interests

- Python, FastAPI, REST APIs
- Static analysis, AST-based tooling
- Web frontends (HTML/CSS/JS)
- DevOps basics: Docker, deployment to Render

How to create/update the profile repo

1. Create a new public repository named `iamaditi2607-svg` on GitHub (exactly your username).
2. Clone it locally, add README.md, push, and then go to your GitHub profile and pin the repository.

Commit attribution and git author settings

- This change preserved the repository's commit history and did not alter existing commits.
- To configure your git author for future commits:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Next steps I recommend (manual)

- Add screenshots to docs/images/ and reference them in README.md.
- Run the test suite locally and fix any failing tests before hackathon submission.
- Consider adding a CONTRIBUTING.md and CODE_OF_CONDUCT.md if you'll accept collaborators.
- If you want, I can also prepare a concise CONTRIBUTING.md and a small demo GIF once you add screenshots.

If you'd like, I can now:

- Update other documentation files (CONTRIBUTING.md, docs/architecture.md) in this repository.
- Create the profile README.md content as a file in a new local repository (I will not push anything to your account without confirmation).

