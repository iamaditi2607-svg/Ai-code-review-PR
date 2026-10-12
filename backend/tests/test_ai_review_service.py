import asyncio

import httpx

from backend.services import ai_review_service


def test_ai_review_sends_bearer_key_to_openai_compatible_endpoint(monkeypatch):
    request_details = {}

    class MockAsyncClient:
        def __init__(self, **kwargs):
            request_details["timeout"] = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            request_details.update(url=url, headers=headers, payload=json)
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"summary":"Review complete","score":90,"findings":[]}'
                            }
                        }
                    ]
                },
            )

    monkeypatch.setenv("LLM_API_KEY", "test-provider-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.example/v1/")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setattr(ai_review_service.httpx, "AsyncClient", MockAsyncClient)

    summary, score, findings = asyncio.run(
        ai_review_service.review_with_llm(
            {
                "repository": "owner/repo",
                "number": 7,
                "review_text": "diff",
            }
        )
    )

    assert request_details["url"] == "https://provider.example/v1/chat/completions"
    assert request_details["headers"]["Authorization"] == "Bearer test-provider-key"
    assert request_details["payload"]["model"] == "test-model"
    assert (summary, score, findings) == ("Review complete", 90, [])
