import os

import httpx
from dotenv import load_dotenv


load_dotenv()

LLM_TIMEOUT_SECONDS = 20.0
LLM_MODEL = "gpt-5-nano"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

api_key = os.getenv("OPENAI_API_KEY")
default_headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
http_client = httpx.Client(timeout=httpx.Timeout(LLM_TIMEOUT_SECONDS, connect=5.0))
ollama_client = httpx.Client(
    base_url=OLLAMA_BASE_URL,
    timeout=httpx.Timeout(LLM_TIMEOUT_SECONDS, connect=5.0),
)


class LLMProviderError(RuntimeError):
    pass


class HostedCallsDisabledError(LLMProviderError):
    pass


class ProviderUnavailableError(LLMProviderError):
    pass


class EmptyResponseError(LLMProviderError):
    pass


def _format_response_body(response):
    try:
        data = response.json()
    except ValueError:
        text = response.text.strip()
        return text or "<empty response body>"

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            parts = []
            for key in ("message", "type", "param", "code"):
                value = error.get(key)
                if value:
                    parts.append(f"{key}={value}")
            if parts:
                return "; ".join(parts)

    return str(data)


def create_response(
    model,
    input_data,
    *,
    max_output_tokens=None,
    reasoning_effort="low",
    stop_sequences=None,
):
    payload = {
        "model": model,
        "input": input_data,
    }
    if max_output_tokens is not None:
        payload["max_output_tokens"] = max_output_tokens
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    if stop_sequences:
        payload["stop"] = stop_sequences

    response = http_client.post(
        "https://api.openai.com/v1/responses",
        headers=default_headers,
        json=payload,
    )
    if response.status_code == 400:
        raise LLMProviderError(f"OpenAI 400 response: {_format_response_body(response)}")
    if response.status_code == 429:
        raise LLMProviderError(f"OpenAI 429 response: {_format_response_body(response)}")
    response.raise_for_status()
    return response.json()


def extract_output_text(response_json):
    output_text = response_json.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    chunks = []
    for item in response_json.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text = content.get("text", "")
                if text:
                    chunks.append(text)

    return "".join(chunks).strip()


def _build_result(*, text, provider, model, fallback_used, attempted_provider=None, fallback_reason=None):
    return {
        "text": text,
        "provider": provider,
        "model": model,
        "fallback_used": fallback_used,
        "attempted_provider": attempted_provider or provider,
        "fallback_reason": fallback_reason,
    }


def _normalize_messages(input_data):
    if isinstance(input_data, str):
        return [{"role": "user", "content": input_data}]
    if isinstance(input_data, list):
        return input_data
    raise TypeError(f"Unsupported input type for generation: {type(input_data).__name__}")


def _require_non_empty_text(text, provider_name):
    if not isinstance(text, str) or not text.strip():
        raise EmptyResponseError(f"{provider_name} returned empty output.")
    return text.strip()


def _generate_openai(
    input_data,
    *,
    model=None,
    max_output_tokens=None,
    reasoning_effort="low",
    stop_sequences=None,
):
    if not api_key:
        raise ProviderUnavailableError("OpenAI API key is missing.")

    resolved_model = model or LLM_MODEL
    response = create_response(
        resolved_model,
        input_data,
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
        stop_sequences=stop_sequences,
    )
    text = extract_output_text(response)
    if not isinstance(text, str) or not text.strip():
        raise EmptyResponseError(f"OpenAI returned empty output. Raw response: {response}")
    text = text.strip()
    return _build_result(
        text=text,
        provider="openai",
        model=resolved_model,
        fallback_used=False,
    )


def _extract_ollama_text(response_json):
    message = response_json.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

    response_text = response_json.get("response")
    if isinstance(response_text, str) and response_text.strip():
        return response_text.strip()

    return ""


def _generate_ollama(input_data, *, model=None, max_output_tokens=None):
    resolved_model = model or OLLAMA_MODEL
    messages = _normalize_messages(input_data)

    try:
        payload = {
            "model": resolved_model,
            "messages": messages,
            "stream": False,
        }
        if max_output_tokens is not None:
            payload["options"] = {"num_predict": max_output_tokens}

        response = ollama_client.post("/api/chat", json=payload)
        response.raise_for_status()
    except httpx.ConnectError as exc:
        raise ProviderUnavailableError(f"Ollama unavailable: {exc}") from exc
    except httpx.TimeoutException as exc:
        raise ProviderUnavailableError(f"Ollama timed out: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise ProviderUnavailableError(f"Ollama HTTP error: {exc}") from exc
    except httpx.HTTPError as exc:
        raise LLMProviderError(f"Ollama transport error: {exc}") from exc

    text = _require_non_empty_text(_extract_ollama_text(response.json()), "Ollama")
    return _build_result(
        text=text,
        provider="ollama",
        model=resolved_model,
        fallback_used=False,
    )


def _is_fallback_eligible(error):
    return isinstance(
        error,
        (
            ProviderUnavailableError,
            EmptyResponseError,
            httpx.HTTPError,
            httpx.TimeoutException,
            TimeoutError,
        ),
    )


def generate_text(
    input_data,
    *,
    provider="openai",
    connection="api",
    model=None,
    max_output_tokens=None,
    reasoning_effort="low",
    stop_sequences=None,
):
    if provider == "openai":
        if connection != "api":
            raise HostedCallsDisabledError("OpenAI calls are disabled when connection=local.")
        return _generate_openai(
            input_data,
            model=model,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
            stop_sequences=stop_sequences,
        )

    if provider == "ollama":
        return _generate_ollama(
            input_data,
            model=model,
            max_output_tokens=max_output_tokens,
        )

    if provider != "auto":
        raise ValueError(f"Unsupported provider: {provider}")

    first_error = None
    try:
        return _generate_ollama(
            input_data,
            model=model,
            max_output_tokens=max_output_tokens,
        )
    except Exception as exc:
        first_error = exc
        if connection != "api":
            raise
        if not _is_fallback_eligible(exc):
            raise

    fallback_result = _generate_openai(
        input_data,
        model=model,
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
        stop_sequences=stop_sequences,
    )
    fallback_result["fallback_used"] = True
    fallback_result["attempted_provider"] = "ollama"
    fallback_result["fallback_reason"] = str(first_error)
    return fallback_result
