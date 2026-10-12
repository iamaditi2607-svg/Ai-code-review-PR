from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


Severity = Literal["Critical", "High", "Medium", "Low"]


class AccessRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class ReviewRequest(BaseModel):
    sample_id: str | None = Field(default=None, max_length=100)
    repository_url: str | None = Field(default=None, max_length=500)
    pull_request_number: int | None = Field(default=None, ge=1, le=10_000_000)
    code_snippet: str | None = Field(default=None, max_length=30_000)

    @field_validator("repository_url")
    @classmethod
    def validate_github_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parsed = HttpUrl(value)
        if parsed.host not in {"github.com", "www.github.com"}:
            raise ValueError("Enter a repository URL hosted on github.com.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2 or any(part in {".", ".."} for part in parts):
            raise ValueError("Use a repository URL in the form https://github.com/owner/repository.")
        if parts[1].endswith(".git"):
            parts[1] = parts[1][:-4]
        if not all(parts):
            raise ValueError("The GitHub repository owner and name are required.")
        return f"https://github.com/{parts[0]}/{parts[1]}"


class Finding(BaseModel):
    id: str
    severity: Severity
    category: str
    title: str
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    explanation: str
    why_it_matters: str
    recommendation: str
    suggested_code: str | None = None
    source: str


class DiffFile(BaseModel):
    filename: str
    old: str
    new: str
    patch: str | None = None


class ReviewResponse(BaseModel):
    id: str
    repository: str
    pull_request_number: int
    title: str
    author: str
    branch: str
    status: str
    summary: str
    score: int = Field(ge=0, le=100)
    score_label: str = "Estimated code quality"
    mode: str
    reviewed_at: str
    files: list[DiffFile]
    findings: list[Finding]


class SamplePullRequest(BaseModel):
    id: str
    title: str
    repository: str
    number: int
    author: str
    branch: str
    updated: str
    status: str
    summary: str
    score: int
    findings_count: int
    files_count: int
