import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.schemas import DiffFile, Finding, ReviewResponse, SamplePullRequest
from backend.services.diff_service import make_unified_patch


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_reviews.json"


def load_samples() -> list[dict]:
    with DATA_PATH.open(encoding="utf-8") as sample_file:
        return json.load(sample_file)


def list_samples() -> list[SamplePullRequest]:
    return [
        SamplePullRequest(
            **{
                key: sample[key]
                for key in (
                    "id",
                    "title",
                    "repository",
                    "number",
                    "author",
                    "branch",
                    "updated",
                    "status",
                    "summary",
                    "score",
                )
            },
            findings_count=len(sample["findings"]),
            files_count=len(sample["files"]),
        )
        for sample in load_samples()
    ]


def get_sample(sample_id: str) -> dict | None:
    return next((sample for sample in load_samples() if sample["id"] == sample_id), None)


def sample_review(sample_id: str | None = None) -> ReviewResponse:
    samples = load_samples()
    sample = next((item for item in samples if item["id"] == sample_id), samples[0])
    return _response_from_sample(sample)


def custom_demo_review(
    code_snippet: str,
    filename: str = "snippet",
    include_empty: bool = True,
) -> ReviewResponse:
    findings: list[Finding] = []
    checks = (
        (
            re.compile(r"\beval\s*\("),
            "High",
            "Security",
            "Dynamic evaluation of input",
            "This snippet calls eval(), which interprets a string as code.",
            "If the value can be influenced by an untrusted caller, arbitrary code execution may be possible. This is a heuristic, not a verified exploit.",
            "Avoid evaluating strings. Parse an expected data format or use an explicit allowlist of operations.",
            "result = json.loads(value)",
        ),
        (
            re.compile(r"\bexecute\s*\([^)]*(?:\+|%s|\.format\s*\()"),
            "High",
            "Security",
            "Query may be assembled dynamically",
            "A query-like execute() call appears to build its command using interpolation or concatenation.",
            "Dynamic query construction can create injection risk when inputs are untrusted; this pattern alone does not confirm exploitability.",
            "Use the database driver's parameter binding and validate the expected input type.",
            'cursor.execute("SELECT * FROM items WHERE id=%s", (item_id,))',
        ),
        (
            re.compile(r"\bshell\s*=\s*True"),
            "High",
            "Security",
            "Shell execution is enabled",
            "subprocess is configured to invoke a shell.",
            "Shell metacharacters in untrusted arguments can change the command being executed. Review the input flow before concluding this is exploitable.",
            "Pass an argument list to subprocess and keep shell=False; validate arguments against the expected format.",
            'subprocess.run(["tool", validated_argument], check=True)',
        ),
        (
            re.compile(r"\bexcept\s*:\s*(?:pass\s*)?(?:$|\n)"),
            "Medium",
            "Reliability",
            "Exception is swallowed broadly",
            "A bare exception handler may catch process-control exceptions and hide unrelated failures.",
            "Unexpected failures can be silently ignored, making production issues difficult to detect.",
            "Catch the specific exceptions expected here and log or propagate unexpected failures.",
            "except (ValueError, TypeError) as error:\n    logger.warning(\"Invalid input: %s\", error)",
        ),
    )
    for pattern, severity, category, title, explanation, why, recommendation, suggestion in checks:
        match = pattern.search(code_snippet)
        if match:
            line = code_snippet.count("\n", 0, match.start()) + 1
            findings.append(
                Finding(
                    id=f"heuristic-{len(findings) + 1}",
                    severity=severity,
                    category=category,
                    title=title,
                    file=filename,
                    line=line,
                    explanation=explanation,
                    why_it_matters=why,
                    recommendation=recommendation,
                    suggested_code=suggestion,
                    source="Demo heuristic",
                )
            )

    if not findings and include_empty:
        findings.append(
            Finding(
                id="heuristic-clean",
                severity="Low",
                category="Best practice",
                title="No configured demo patterns matched",
                file=filename,
                line=None,
                explanation="The demo engine checks a small set of common patterns; it does not understand the full program.",
                why_it_matters="A clean heuristic result is not proof that code is correct, safe, or production-ready.",
                recommendation="Review edge cases, input validation, tests, and behavior in the context of the complete repository.",
                source="Demo heuristic",
            )
        )

    files = [DiffFile(filename=filename, old="", new=code_snippet, patch=make_unified_patch("", code_snippet, filename))]
    return ReviewResponse(
        id=str(uuid4()),
        repository="demo/custom-snippet",
        pull_request_number=1,
        title="Custom snippet review",
        author="demo-user",
        branch="demo/snippet",
        status="Completed",
        summary=f"The demo heuristic matched {len(findings)} review pattern(s). Results are illustrative, not a full code audit.",
        score=max(35, 100 - (len(findings) * 12)),
        mode="Demo heuristic",
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        files=files,
        findings=findings,
    )


def _response_from_sample(sample: dict) -> ReviewResponse:
    files = [
        DiffFile(
            filename=item["filename"],
            old=item["old"],
            new=item["new"],
            patch=make_unified_patch(item["old"], item["new"], item["filename"]),
        )
        for item in sample["files"]
    ]
    return ReviewResponse(
        id=str(uuid4()),
        repository=sample["repository"],
        pull_request_number=sample["number"],
        title=sample["title"],
        author=sample["author"],
        branch=sample["branch"],
        status=sample["status"],
        summary=sample["summary"],
        score=sample["score"],
        mode="Demo data",
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        files=files,
        findings=[Finding(**finding) for finding in sample["findings"]],
    )
