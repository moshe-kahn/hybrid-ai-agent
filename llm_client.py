import os

import httpx
from dotenv import load_dotenv


load_dotenv()

LLM_TIMEOUT_SECONDS = 20.0
LLM_MODEL = "gpt-5-nano"

api_key = os.getenv("OPENAI_API_KEY")
default_headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
http_client = httpx.Client(timeout=httpx.Timeout(LLM_TIMEOUT_SECONDS, connect=5.0))


def create_response(model, input_data):
    response = http_client.post(
        "https://api.openai.com/v1/responses",
        headers=default_headers,
        json={"model": model, "input": input_data},
    )
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
