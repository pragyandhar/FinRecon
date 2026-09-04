import json
import time
from abc import ABC, abstractmethod
from typing import Callable

from app.core.config import settings
from app.core.errors import ModelExecutionFailedError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Every AI stage in FinRecon (schema understanding, canonical mapping,
# planning, plan repair, exception investigation, chat) calls through
# this one interface with one configured model — settings.openai_model,
# read from OPENAI_MODEL in .env. There is deliberately no separate
# "SLM model" / "LLM model" env var: change OPENAI_MODEL once and every
# call site picks it up.


class ModelClient(ABC):
    @abstractmethod
    def complete_json(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        job_id: str | None = None,
        on_usage: Callable[[int, int], None] | None = None,
    ) -> dict:
        """Sends one prompt, returns a parsed JSON object. Raises
        ModelExecutionFailedError on failure (bad JSON, API error,
        timeout after retry) — callers never receive a partial/garbage
        dict silently."""


class OpenAIModelClient(ModelClient):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ModelExecutionFailedError(
                "OPENAI_API_KEY is not set — cannot make AI calls. "
                "Set it in .env or use a FakeModelClient for tests."
            )
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    def complete_json(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        job_id: str | None = None,
        on_usage: Callable[[int, int], None] | None = None,
    ) -> dict:
        last_error: Exception | None = None
        for attempt in range(2):  # one retry on transient failure — no unbounded loops
            start = time.monotonic()
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    temperature=0,
                    timeout=60,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                latency_ms = int((time.monotonic() - start) * 1000)
                content = response.choices[0].message.content
                usage = response.usage
                if on_usage and usage:
                    on_usage(usage.prompt_tokens, usage.completion_tokens)
                logger.info(
                    "model_call stage=%s model=%s latency_ms=%d prompt_tokens=%s completion_tokens=%s",
                    stage,
                    self._model,
                    latency_ms,
                    getattr(usage, "prompt_tokens", None),
                    getattr(usage, "completion_tokens", None),
                )
                return json.loads(content)
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.warning("model_call stage=%s returned invalid JSON (attempt %d)", stage, attempt + 1)
            except Exception as exc:  # noqa: BLE001 — any SDK/API failure funnels into one error type
                last_error = exc
                logger.warning("model_call stage=%s failed (attempt %d): %s", stage, attempt + 1, exc)
        raise ModelExecutionFailedError(f"model call for stage '{stage}' failed: {last_error}")


class FakeModelClient(ModelClient):
    """Deterministic, zero-network stand-in used by the automated test
    suite so tests never spend the real API budget. Returns whatever
    canned response was registered for a stage."""

    def __init__(self, responses: dict[str, dict | list[dict]] | None = None) -> None:
        self._responses = responses or {}
        self._call_counts: dict[str, int] = {}
        self.calls: list[dict] = []

    def complete_json(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        job_id: str | None = None,
        on_usage: Callable[[int, int], None] | None = None,
    ) -> dict:
        self.calls.append({"stage": stage, "system": system, "user": user, "job_id": job_id})
        if on_usage:
            on_usage(0, 0)
        response = self._responses.get(stage)
        if response is None:
            raise ModelExecutionFailedError(f"FakeModelClient has no canned response for stage '{stage}'")
        if isinstance(response, list):
            idx = self._call_counts.get(stage, 0)
            self._call_counts[stage] = idx + 1
            return response[min(idx, len(response) - 1)]
        return response


_singleton: ModelClient | None = None


def get_model_client() -> ModelClient:
    global _singleton
    if _singleton is None:
        _singleton = OpenAIModelClient()
    return _singleton
