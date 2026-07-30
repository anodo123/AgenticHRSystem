"""Tests for production OpenAI Responses API request/response handling."""
import json

import httpx
import pytest

from app.llm import LLMConfigurationError, LLMResponseError, OpenAIResponsesClient


@pytest.mark.real_llm_client
def test_responses_client_sends_bearer_auth_and_strict_schema():
    captured = {}

    def handler(request: httpx.Request):
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, request=request, json={
            "id": "resp_test",
            "status": "completed",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": '{"decision":"ALLOW"}'}],
            }],
        })

    client = OpenAIResponsesClient(
        api_key="test-key", model="gpt-test", max_retries=0,
        transport=httpx.MockTransport(handler),
    )
    result = client.generate(
        agent_name="compliance",
        system_prompt="Return a decision.",
        context={"workflow_id": "WF-1"},
        candidate={"decision": "ALLOW"},
        schema={
            "type": "object",
            "properties": {"decision": {"type": "string"}},
            "required": ["decision"],
            "additionalProperties": False,
        },
    )
    assert result == {"decision": "ALLOW"}
    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "gpt-test"
    assert captured["body"]["text"]["format"]["strict"] is True
    assert captured["body"]["metadata"]["workflow_id"] == "WF-1"
    assert captured["body"]["max_output_tokens"] == 2000


@pytest.mark.real_llm_client
def test_missing_key_and_refusal_fail_closed():
    client = OpenAIResponsesClient(api_key="", max_retries=0)
    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY"):
        client.generate(
            agent_name="policy", system_prompt="x", context={},
            candidate={}, schema={"type": "object"},
        )
    with pytest.raises(LLMResponseError, match="refused"):
        OpenAIResponsesClient._extract({
            "status": "completed",
            "output": [{"type": "message", "content": [
                {"type": "refusal", "refusal": "unsafe request"}
            ]}],
        })
