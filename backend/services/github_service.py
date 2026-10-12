import os
import re
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from backend.schemas import DiffFile


GITHUB_API = "https://api.github.com"
FILES_PER_PAGE = 100
MAX_FILE_PAGES = 30


def parse_repository_url(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        raise HTTPException(status_code=422, detail="Enter a valid https://github.com/owner/repository URL.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="Use a repository URL in the form https://github.com/owner/repository.")
    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repository):
        raise HTTPException(status_code=422, detail="The GitHub repository URL contains invalid characters.")
    return owner, repository


async def fetch_pull_request(repository_url: str, number: int) -> dict:
    owner, repository = parse_repository_url(repository_url)
    token = os.getenv("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        try:
            pr_response = await client.get(f"{GITHUB_API}/repos/{owner}/{repository}/pulls/{number}", headers=headers)
            _raise_github_error(pr_response)
            pr = pr_response.json()
            changed_files = []
            for page in range(1, MAX_FILE_PAGES + 1):
                files_response = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repository}/pulls/{number}/files",
                    headers=headers,
                    params={"per_page": FILES_PER_PAGE, "page": page},
                )
                _raise_github_error(files_response)
                page_files = files_response.json()
                if not isinstance(page_files, list):
                    raise HTTPException(status_code=502, detail="GitHub returned an invalid changed-files response.")
                changed_files.extend(page_files)
                if len(page_files) < FILES_PER_PAGE:
                    break
        except httpx.TimeoutException as error:
            raise HTTPException(status_code=504, detail="GitHub did not respond in time. Please retry shortly.") from error
        except httpx.RequestError as error:
            raise HTTPException(status_code=502, detail="Could not connect to GitHub. Check your network and retry.") from error
        except ValueError as error:
            raise HTTPException(status_code=502, detail="GitHub returned an unreadable response.") from error

    files = []
    for changed_file in changed_files:
        if not isinstance(changed_file, dict):
            raise HTTPException(status_code=502, detail="GitHub returned an invalid changed-file entry.")
        filename = str(changed_file.get("filename", "unknown"))
        patch = changed_file.get("patch")
        files.append(
            DiffFile(
                filename=filename,
                old="",
                new="",
                patch=patch,
            )
        )

    return {
        "repository": f"{owner}/{repository}",
        "number": number,
        "title": str(pr.get("title", f"Pull request #{number}"))[:300],
        "author": str(pr.get("user", {}).get("login", "unknown"))[:100],
        "branch": str(pr.get("head", {}).get("ref", "unknown"))[:200],
        "files": files,
        "review_text": _build_review_text(files),
    }


def _build_review_text(files: list[DiffFile]) -> str:
    pieces = []
    for item in files:
        pieces.append(f"File: {item.filename}\n")
        pieces.append(item.patch or "[Patch unavailable for this file.]\n")
    return "\n".join(pieces)


def _raise_github_error(response: httpx.Response) -> None:
    if response.is_success:
        return
    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Pull request or repository not found. For private repositories, configure a token with repository read access.",
        )
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="GitHub rejected the configured token. Check GITHUB_TOKEN permissions.")
    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            raise HTTPException(status_code=429, detail="GitHub API rate limit reached. Wait for the reset or configure GITHUB_TOKEN.")
        raise HTTPException(
            status_code=403,
            detail="GitHub denied access. Check token permissions and repository access.",
        )
    if response.status_code == 429:
        raise HTTPException(status_code=429, detail="GitHub API rate limit reached. Please retry later.")
    raise HTTPException(status_code=502, detail=f"GitHub API request failed with status {response.status_code}.")
