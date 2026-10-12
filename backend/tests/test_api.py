import base64

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_optional_password_gate_protects_dashboard_and_static_app(monkeypatch):
    monkeypatch.setenv("CODE_SENTINEL_USERNAME", "judge")
    monkeypatch.setenv("CODE_SENTINEL_PASSWORD", "test-password")
    unauthorized = client.get("/api/dashboard")
    assert unauthorized.status_code == 401
    login_page = client.get("/")
    assert login_page.status_code == 200
    assert "password-protected" in login_page.text

    credentials = base64.b64encode(b"judge:test-password").decode("ascii")
    authorized = client.get("/", headers={"Authorization": f"Basic {credentials}"})
    assert authorized.status_code == 200
    assert "AI Code Review Bot (GitHub PR)" in authorized.text


def test_password_login_issues_http_only_session_cookie(monkeypatch):
    monkeypatch.setenv("CODE_SENTINEL_USERNAME", "judge")
    monkeypatch.setenv("CODE_SENTINEL_PASSWORD", "test-password")
    with TestClient(app) as auth_client:
        rejected = auth_client.post(
            "/api/access",
            json={"username": "judge", "password": "incorrect"},
        )
        assert rejected.status_code == 401

        accepted = auth_client.post(
            "/api/access",
            json={"username": "judge", "password": "test-password"},
        )
        assert accepted.status_code == 200
        assert accepted.cookies["codesentinel_session"]
        assert "httponly" in accepted.headers["set-cookie"].lower()
        assert auth_client.get("/api/dashboard").status_code == 200


def test_public_health_check_works_with_password_gate_enabled(monkeypatch):
    monkeypatch.setenv("CODE_SENTINEL_USERNAME", "judge")
    monkeypatch.setenv("CODE_SENTINEL_PASSWORD", "test-password")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_partial_password_gate_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("CODE_SENTINEL_USERNAME", "judge")
    monkeypatch.delenv("CODE_SENTINEL_PASSWORD", raising=False)
    response = client.get("/api/health")
    assert response.status_code == 503


def test_health_reports_demo_mode_without_secrets(monkeypatch):
    monkeypatch.delenv("CODE_SENTINEL_USERNAME", raising=False)
    monkeypatch.delenv("CODE_SENTINEL_PASSWORD", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "demo_mode": True,
        "github_token_configured": False,
        "llm_configured": False,
    }
    assert client.get("/health").json() == response.json()


def test_root_and_frontend_assets_are_served_from_fastapi():
    homepage = client.get("/")
    stylesheet = client.get("/style.css")
    application = client.get("/app.js")

    assert homepage.status_code == 200
    assert "AI Code Review Bot (GitHub PR)" in homepage.text
    assert stylesheet.status_code == 200
    assert application.status_code == 200
    assert "renderReviewInsights" in application.text


def test_dashboard_and_samples_are_available():
    dashboard = client.get("/api/dashboard")
    samples = client.get("/api/samples")
    assert dashboard.status_code == 200
    assert dashboard.json()["data_label"] == "Demo dashboard data"
    assert dashboard.json()["quality_score"] >= 0
    assert len(samples.json()) >= 1
    assert samples.json()[0]["findings_count"] >= 1


def test_demo_sample_review_includes_findings_and_diff(monkeypatch, tmp_path):
    from backend.services import review_history

    monkeypatch.setattr(review_history, "DATABASE_PATH", tmp_path / "reviews.sqlite3")
    response = client.post("/api/review/demo", json={"sample_id": "python-api-validation"})
    assert response.status_code == 200
    review = response.json()
    assert review["mode"] == "Demo data"
    assert review["score_label"] == "Estimated code quality"
    assert review["findings"][0]["source"] == "Demo heuristic"
    assert review["files"][0]["patch"].startswith("--- a/")


def test_custom_snippet_uses_safe_labeled_heuristics(monkeypatch, tmp_path):
    from backend.services import review_history

    monkeypatch.setattr(review_history, "DATABASE_PATH", tmp_path / "reviews.sqlite3")
    response = client.post("/api/review/demo", json={"code_snippet": "eval(user_input)\n"})
    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["severity"] == "High"
    assert finding["line"] == 1
    assert finding["source"] == "Demo heuristic"
    assert "not a verified exploit" in finding["why_it_matters"]


def test_bad_sample_returns_clear_not_found():
    response = client.post("/api/review/demo", json={"sample_id": "missing"})
    assert response.status_code == 404
    assert "available sample" in response.json()["detail"]


def test_invalid_repository_url_is_rejected():
    response = client.post(
        "/api/review/github",
        json={"repository_url": "https://example.com/owner/repo", "pull_request_number": 1},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("status_code", "headers", "expected_status", "message_fragment"),
    [
        (401, {}, 401, "rejected the configured token"),
        (403, {"X-RateLimit-Remaining": "0"}, 429, "rate limit reached"),
        (403, {}, 403, "denied access"),
        (404, {}, 404, "not found"),
        (429, {}, 429, "rate limit reached"),
    ],
)
def test_github_api_errors_are_reported_clearly(
    monkeypatch,
    status_code,
    headers,
    expected_status,
    message_fragment,
):
    from backend.services import github_service

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return httpx.Response(status_code, headers=headers, json={"message": "mocked GitHub error"})

    monkeypatch.setattr(github_service.httpx, "AsyncClient", MockAsyncClient)
    response = client.post(
        "/api/review/github",
        json={"repository_url": "https://github.com/octocat/Hello-World", "pull_request_number": 1},
    )

    assert response.status_code == expected_status
    assert message_fragment in response.json()["detail"].lower()


def test_github_timeout_is_returned_as_gateway_timeout(monkeypatch):
    from backend.services import github_service

    class TimeoutAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            request = httpx.Request("GET", "https://api.github.com/repos/octocat/Hello-World/pulls/1")
            raise httpx.ReadTimeout("mocked timeout", request=request)

    monkeypatch.setattr(github_service.httpx, "AsyncClient", TimeoutAsyncClient)
    response = client.post(
        "/api/review/github",
        json={"repository_url": "https://github.com/octocat/Hello-World", "pull_request_number": 1},
    )

    assert response.status_code == 504
    assert "did not respond in time" in response.json()["detail"]


def test_github_repository_url_is_normalized():
    from backend.schemas import ReviewRequest

    request = ReviewRequest(repository_url="https://github.com/octocat/Hello-World.git")
    assert request.repository_url == "https://github.com/octocat/Hello-World"


def test_demo_requires_sample_or_snippet():
    response = client.post("/api/review/demo", json={"repository_url": "https://github.com/a/b"})
    assert response.status_code == 422


def test_python_code_samples_include_bug_security_and_clean_cases():
    response = client.get("/api/code-samples")
    assert response.status_code == 200
    samples = response.json()
    assert len(samples) >= 3
    assert {sample["category"] for sample in samples} >= {
        "Potential bug",
        "Security pattern",
        "Clean example",
    }


def test_each_builtin_code_sample_runs_through_python_rules(monkeypatch, tmp_path):
    from backend.services import python_analyzer, review_history

    monkeypatch.setattr(review_history, "DATABASE_PATH", tmp_path / "reviews.sqlite3")
    samples = {sample["category"]: sample for sample in python_analyzer.load_python_samples()}
    expected = {
        "Potential bug": True,
        "Security pattern": True,
        "Clean example": False,
    }
    for category, should_find_issue in expected.items():
        response = client.post(
            "/api/review/code",
            json={"code_snippet": samples[category]["code"]},
        )
        assert response.status_code == 200
        assert bool(response.json()["findings"]) is should_find_issue


def test_code_review_detects_mutable_default_with_line_and_fix(monkeypatch, tmp_path):
    from backend.services import review_history

    monkeypatch.setattr(review_history, "DATABASE_PATH", tmp_path / "reviews.sqlite3")
    response = client.post(
        "/api/review/code",
        json={"code_snippet": "def collect(item, items=[]):\n    items.append(item)\n    return items\n"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "Python static analysis (AST rules)"
    assert result["findings"][0]["severity"] == "Medium"
    assert result["findings"][0]["line"] == 1
    assert result["findings"][0]["source"] == "Python AST rules v1"
    assert "None" in result["findings"][0]["suggested_code"]


def test_code_review_detects_eval_without_executing_source(monkeypatch, tmp_path):
    from backend.services import review_history

    monkeypatch.setattr(review_history, "DATABASE_PATH", tmp_path / "reviews.sqlite3")
    response = client.post(
        "/api/review/code",
        json={"code_snippet": "result = eval(user_input)\n"},
    )
    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["severity"] == "High"
    assert finding["line"] == 1
    assert "not verified" in finding["why_it_matters"]


def test_clean_code_returns_no_findings(monkeypatch, tmp_path):
    from backend.services import review_history

    monkeypatch.setattr(review_history, "DATABASE_PATH", tmp_path / "reviews.sqlite3")
    response = client.post(
        "/api/review/code",
        json={"code_snippet": "def safe_add(left, right):\n    return left + right\n"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["findings"] == []
    assert result["summary"] == "No issues were detected by the configured Python AST rules."


def test_invalid_python_is_reported_as_syntax_error(monkeypatch, tmp_path):
    from backend.services import review_history

    monkeypatch.setattr(review_history, "DATABASE_PATH", tmp_path / "reviews.sqlite3")
    response = client.post("/api/review/code", json={"code_snippet": "def broken(:\n"})
    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["category"] == "Syntax"
    assert finding["line"] == 1


def test_submitted_python_is_parsed_but_never_executed(monkeypatch, tmp_path):
    from backend.services import review_history

    monkeypatch.setattr(review_history, "DATABASE_PATH", tmp_path / "reviews.sqlite3")
    marker = tmp_path / "execution-marker.txt"
    source = f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
    response = client.post("/api/review/code", json={"code_snippet": source})
    assert response.status_code == 200
    assert not marker.exists()


def test_code_review_requires_non_empty_source():
    response = client.post("/api/review/code", json={"code_snippet": "   \n"})
    assert response.status_code == 422


def test_review_history_is_saved_and_clearable(monkeypatch, tmp_path):
    from backend.services import review_history

    monkeypatch.setattr(review_history, "DATABASE_PATH", tmp_path / "reviews.sqlite3")
    reviewed = client.post(
        "/api/review/code",
        json={"code_snippet": "def simple():\n    return 1\n"},
    )
    assert reviewed.status_code == 200
    history = client.get("/api/reviews")
    assert history.status_code == 200
    assert history.json()[0]["id"] == reviewed.json()["id"]
    cleared = client.delete("/api/reviews")
    assert cleared.status_code == 200
    assert client.get("/api/reviews").json() == []
