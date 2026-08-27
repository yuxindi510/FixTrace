import json

from fixtrace.agent.provider import OpenAIResponsesModel


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_openai_provider_uses_responses_api_without_storage(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return _Response(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": '{"action":"finalize"}'}],
                    }
                ]
            }
        )

    monkeypatch.setattr("fixtrace.agent.provider.urlopen", fake_urlopen)
    provider = OpenAIResponsesModel(
        api_key="test-key-not-real",
        model="test-model",
        base_url="https://api.openai.com/v1",
        timeout_seconds=42,
    )

    result = provider.complete(
        [
            {"role": "system", "content": "Return JSON."},
            {"role": "user", "content": "Investigate."},
        ]
    )

    assert result == '{"action":"finalize"}'
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["body"]["model"] == "test-model"
    assert captured["body"]["store"] is False
    assert captured["timeout"] == 42
