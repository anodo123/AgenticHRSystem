"""Synchronous OpenAI Responses API client with strict structured outputs."""
import json
from time import sleep
from typing import Any

import httpx

from app.core.config import get_settings


class LLMConfigurationError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


class OpenAIResponsesClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.model = model or settings.llm_model
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.timeout = timeout or settings.llm_timeout_seconds
        self.max_retries = (
            max_retries if max_retries is not None else settings.llm_max_retries
        )
        self.transport = transport

    def generate(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        context: dict[str, Any],
        candidate: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY is required; no mock LLM fallback is configured"
            )
        body = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": json.dumps(
                            {"workflow_context": context, "validated_facts": candidate},
                            default=str,
                        ),
                    }],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": f"{agent_name}_result",
                    "strict": True,
                    "schema": schema,
                }
            },
            "reasoning": {"effort": get_settings().llm_reasoning_effort},
            "max_output_tokens": get_settings().llm_max_output_tokens,
            "metadata": {
                "workflow_id": str(context.get("workflow_id", ""))[:512],
                "agent": agent_name,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(
                    timeout=self.timeout, transport=self.transport
                ) as client:
                    response = client.post(
                        f"{self.base_url}/responses", headers=headers, json=body
                    )
                if response.status_code in {408, 409, 429} or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "retryable OpenAI response", request=response.request,
                        response=response,
                    )
                if response.is_error:
                    request_id = response.headers.get("x-request-id", "unknown")
                    raise LLMResponseError(
                        f"OpenAI rejected request ({response.status_code}, "
                        f"request_id={request_id})"
                    )
                return self._extract(response.json())
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                sleep(min(2 ** attempt, 4))
        raise LLMResponseError(f"OpenAI Responses API failed: {last_error}") from last_error

    @staticmethod
    def _extract(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("status") == "incomplete":
            raise LLMResponseError(
                f"OpenAI response incomplete: {payload.get('incomplete_details')}"
            )
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "refusal":
                    raise LLMResponseError(f"OpenAI refused request: {content.get('refusal')}")
                if content.get("type") == "output_text":
                    try:
                        value = json.loads(content["text"])
                    except (KeyError, json.JSONDecodeError) as exc:
                        raise LLMResponseError("OpenAI returned invalid structured JSON") from exc
                    if not isinstance(value, dict):
                        raise LLMResponseError("OpenAI structured output must be an object")
                    return value
        raise LLMResponseError("OpenAI response contained no output_text")
