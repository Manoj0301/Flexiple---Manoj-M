import asyncio
import logging
import os
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.errors import AppError

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

# Luna is the fast tier for extraction and scoring. Astra was correct but too slow for this loop.
MODELS = ("gpt-5.6-luna", "gpt-5.6-terra")


def _provider_error(exc: Exception) -> AppError:
    text = str(exc)
    lowered = text.lower()
    if "quota" in lowered or "insufficient_quota" in lowered or "billing" in lowered:
        return AppError(
            "LLM_RATE_LIMITED",
            "This OpenAI key has no remaining quota. Check billing, then retry. Your last results are unchanged.",
            True,
            429,
        )
    if "429" in text or "rate limit" in lowered or "503" in text or "overloaded" in lowered:
        return AppError(
            "LLM_RATE_LIMITED",
            "The AI service is temporarily busy. Your last results are unchanged.",
            True,
            429,
        )
    if isinstance(exc, TimeoutError) or "timeout" in lowered or "timed out" in lowered:
        return AppError(
            "LLM_TIMEOUT",
            "The AI service timed out. Your last results are unchanged.",
            True,
            504,
        )
    return AppError(
        "LLM_UNAVAILABLE",
        "The AI service could not complete the request. Your last results are unchanged.",
        True,
        502,
    )


class OpenAIClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self._client = None

    def _sdk(self):
        if not self.api_key:
            raise AppError(
                "MISSING_API_KEY",
                "Set OPENAI_API_KEY in backend/.env. A ChatGPT login is not this key.",
                False,
                500,
            )
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key, timeout=90)
        return self._client

    async def _call(self, prompt: str, schema: type[T]) -> T:
        def run() -> T:
            client = self._sdk()
            last_error: Exception | None = None
            for model in MODELS:
                try:
                    response = client.responses.parse(
                        model=model,
                        input=prompt,
                        text_format=schema,
                    )
                    parsed = response.output_parsed
                    if isinstance(parsed, schema):
                        return parsed
                    if parsed is not None:
                        return schema.model_validate(parsed)
                    raise ValueError("The model returned an empty response.")
                except Exception as exc:
                    last_error = exc
                    text = str(exc).lower()
                    fallback = any(
                        token in text
                        for token in (
                            "404",
                            "model_not_found",
                            "does not exist",
                            "not found",
                            "quota",
                            "insufficient_quota",
                            "429",
                            "503",
                            "overloaded",
                            "timeout",
                            "timed out",
                        )
                    )
                    # A schema or auth failure should not be hidden behind the next model.
                    if "invalid_api_key" in text or "incorrect api key" in text:
                        raise
                    logger.warning("OpenAI %s failed: %s", model, exc)
                    if not fallback:
                        raise
            if last_error is not None:
                raise last_error
            raise ValueError("The model returned an empty response.")

        try:
            return await asyncio.wait_for(asyncio.to_thread(run), timeout=120)
        except AppError:
            raise
        except TimeoutError as exc:
            raise _provider_error(exc) from exc
        except (ValidationError, ValueError):
            raise
        except Exception as exc:
            raise _provider_error(exc) from exc

    async def generate(self, prompt: str, schema: type[T], force: str | None = None) -> T:
        if force == "timeout":
            raise AppError(
                "LLM_TIMEOUT",
                "The AI service timed out. Your last results are unchanged.",
                True,
                504,
            )
        if force == "malformed":
            raise AppError(
                "LLM_INVALID_OUTPUT",
                "The model returned malformed JSON. Your last results are unchanged.",
                True,
                502,
            )
        try:
            return await self._call(prompt, schema)
        except AppError:
            raise
        except (ValidationError, ValueError) as first_error:
            repair = (
                f"{prompt}\n\nThe previous response did not match the required JSON schema. "
                "Return one corrected JSON object and nothing else.\n"
                f"Problem: {first_error}"
            )
            try:
                return await self._call(repair, schema)
            except AppError:
                raise
            except (ValidationError, ValueError) as exc:
                raise AppError(
                    "LLM_INVALID_OUTPUT",
                    "The model returned malformed JSON. Your last results are unchanged.",
                    True,
                    502,
                ) from exc


GeminiClient = OpenAIClient
