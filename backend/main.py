import base64
import binascii
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from backend.schemas import AccessRequest, Finding, ReviewRequest, ReviewResponse
from backend.services import ai_review_service, demo_review_service, github_service, python_analyzer, review_history
from backend.services.diff_service import make_unified_patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SESSION_COOKIE = "codesentinel_session"
SESSION_LIFETIME_SECONDS = 12 * 60 * 60

app = FastAPI(
    title="AI Code Review Bot (GitHub PR)",
    description="Demo-first GitHub pull request review prototype. Reviews are advisory and never change pull requests.",
    version="1.0.0",
)
origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def optional_basic_auth(request: Request, call_next):
    username = os.getenv("CODE_SENTINEL_USERNAME", "")
    password = os.getenv("CODE_SENTINEL_PASSWORD", "")
    if not username and not password:
        return await call_next(request)
    if not username or not password:
        return PlainTextResponse(
            "Set both CODE_SENTINEL_USERNAME and CODE_SENTINEL_PASSWORD to enable access protection.",
            status_code=503,
        )
    if request.method == "OPTIONS" or request.url.path in {"/api/access", "/health"}:
        return await call_next(request)

    if _valid_session(request.cookies.get(SESSION_COOKIE), username, password):
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    encoded_credentials = authorization.removeprefix("Basic ").strip()
    try:
        if not authorization.startswith("Basic ") or not encoded_credentials:
            raise ValueError("Basic credentials are required.")
        decoded = base64.b64decode(encoded_credentials, validate=True).decode("utf-8")
        supplied_username, separator, supplied_password = decoded.partition(":")
        valid_username = secrets.compare_digest(supplied_username, username)
        valid_password = secrets.compare_digest(supplied_password, password)
        if not separator or not valid_username or not valid_password:
            raise ValueError("Credentials are invalid.")
    except (ValueError, UnicodeDecodeError, binascii.Error):
        if request.method == "GET" and request.url.path == "/":
            return FileResponse(FRONTEND_DIR / "login.html")
        return PlainTextResponse(
            "Authentication required.",
            status_code=401,
        )
    return await call_next(request)


def _valid_session(cookie: str | None, username: str, password: str) -> bool:
    if not cookie:
        return False
    try:
        expires_text, supplied_signature = cookie.split(".", maxsplit=1)
        expires_at = int(expires_text)
    except (ValueError, TypeError):
        return False
    if expires_at <= int(time.time()) or expires_at > int(time.time()) + SESSION_LIFETIME_SECONDS:
        return False
    payload = f"{username}:{expires_text}".encode("utf-8")
    expected_signature = hmac.new(password.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return secrets.compare_digest(supplied_signature, expected_signature)


@app.post("/api/access")
async def create_access_session(credentials: AccessRequest, request: Request) -> JSONResponse:
    username = os.getenv("CODE_SENTINEL_USERNAME", "")
    password = os.getenv("CODE_SENTINEL_PASSWORD", "")
    if not username and not password:
        return {"status": "authentication is not enabled"}
    if not username or not password:
        raise HTTPException(status_code=503, detail="Access protection is not configured correctly.")

    if not secrets.compare_digest(credentials.username, username) or not secrets.compare_digest(credentials.password, password):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    expires_at = int(time.time()) + SESSION_LIFETIME_SECONDS
    expires_text = str(expires_at)
    payload = f"{username}:{expires_text}".encode("utf-8")
    signature = hmac.new(password.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    response = JSONResponse({"status": "authenticated"})
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    response.set_cookie(
        SESSION_COOKIE,
        f"{expires_text}.{signature}",
        max_age=SESSION_LIFETIME_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https" or forwarded_proto == "https",
        samesite="strict",
        path="/",
    )
    return response


@app.get("/health", include_in_schema=False)
@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "demo_mode": not ai_review_service.is_configured(),
        "github_token_configured": bool(os.getenv("GITHUB_TOKEN", "").strip()),
        "llm_configured": ai_review_service.is_configured(),
    }


@app.get("/api/dashboard")
async def dashboard() -> dict:
    samples = demo_review_service.list_samples()
    findings = [finding for sample in demo_review_service.load_samples() for finding in sample["findings"]]
    return {
        "total_reviews": 128,
        "bugs_detected": sum(finding["category"] in {"Reliability", "Bug"} for finding in findings) + 24,
        "security_issues": sum(finding["category"] == "Security" for finding in findings) + 18,
        "quality_score": round(sum(sample.score for sample in samples) / len(samples)),
        "recent_reviews": [sample.model_dump() for sample in samples],
        "data_label": "Demo dashboard data",
    }


@app.get("/api/samples")
async def samples() -> list[dict]:
    return [sample.model_dump() for sample in demo_review_service.list_samples()]


@app.get("/api/code-samples")
async def code_samples() -> list[dict[str, str]]:
    return python_analyzer.load_python_samples()


@app.get("/api/reviews", response_model=list[ReviewResponse])
async def reviews() -> list[ReviewResponse]:
    return review_history.list_reviews()


@app.delete("/api/reviews")
async def clear_reviews() -> dict[str, int | str]:
    return {"status": "cleared", "deleted": review_history.clear_reviews()}


@app.post("/api/review/code", response_model=ReviewResponse)
async def review_code(request: ReviewRequest) -> ReviewResponse:
    if request.code_snippet is None or not request.code_snippet.strip():
        raise HTTPException(status_code=422, detail="Paste Python code or select a sample before reviewing.")
    review = python_analyzer.analyze_python_source(request.code_snippet)
    review_history.save_review(review)
    return review


@app.post("/api/review/demo", response_model=ReviewResponse)
async def review_demo(request: ReviewRequest) -> ReviewResponse:
    if request.code_snippet and request.code_snippet.strip():
        review = demo_review_service.custom_demo_review(request.code_snippet)
        review_history.save_review(review)
        return review
    if request.sample_id:
        sample = demo_review_service.get_sample(request.sample_id)
        if sample is None:
            raise HTTPException(status_code=404, detail="Demo pull request not found. Choose one of the available sample pull requests.")
        review = demo_review_service.sample_review(request.sample_id)
        review_history.save_review(review)
        return review
    if request.repository_url or request.pull_request_number:
        raise HTTPException(
            status_code=422,
            detail="A demo review needs a sample pull request or a code snippet. To review a live pull request, use GitHub review.",
        )
    review = demo_review_service.sample_review()
    review_history.save_review(review)
    return review


@app.post("/api/review/github", response_model=ReviewResponse)
async def review_github(request: ReviewRequest) -> ReviewResponse:
    if not request.repository_url:
        raise HTTPException(status_code=422, detail="Enter a GitHub repository URL.")
    if request.pull_request_number is None:
        raise HTTPException(status_code=422, detail="Enter a pull request number greater than zero.")

    pull_request = await github_service.fetch_pull_request(request.repository_url, request.pull_request_number)
    if not pull_request["files"]:
        raise HTTPException(status_code=422, detail="This pull request has no changed files to review.")

    if ai_review_service.is_configured():
        summary, score, findings = await ai_review_service.review_with_llm(pull_request)
        review = ai_review_service.make_ai_response(pull_request, summary, score, findings)
        review_history.save_review(review)
        return review

    files = [
        file.model_copy(
            update={
                "old": "",
                "new": file.patch or "",
                "patch": file.patch or make_unified_patch("", "", file.filename),
            }
        )
        for file in pull_request["files"]
    ]
    findings: list[Finding] = []
    for file in files:
        if not file.patch:
            continue
        added_and_context = "\n".join(
            line[1:]
            for line in file.patch.splitlines()
            if line and not line.startswith(("+++", "---", "@@", "\\"))
            and line[0] in {" ", "+"}
        )
        file_review = demo_review_service.custom_demo_review(
            added_and_context,
            filename=file.filename,
            include_empty=False,
        )
        for finding in file_review.findings:
            finding.id = f"{file.filename}:{len(findings) + 1}"
            finding.line = None
            findings.append(finding)

    if not findings:
        no_match = demo_review_service.custom_demo_review(
            pull_request["review_text"],
            filename="",
        ).findings[0]
        no_match.file = None
        no_match.line = None
        findings.append(no_match)

    review = ReviewResponse(
        id=str(uuid4()),
        repository=pull_request["repository"],
        pull_request_number=pull_request["number"],
        title=pull_request["title"],
        author=pull_request["author"],
        branch=pull_request["branch"],
        status="Completed",
        summary="Live pull request diff retrieved from GitHub. Demo heuristics matched "
        f"{len(findings) if findings[0].title != 'No configured demo patterns matched' else 0} pattern(s); "
        "results are illustrative, not a full code audit.",
        score=max(35, 100 - (len(findings) * 12)),
        mode="Demo heuristic (live GitHub diff)",
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        files=files,
        findings=findings,
    )
    review_history.save_review(review)
    return review


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
