import json
import os
import socket
import sys
import threading
import time

import httpx
from dotenv import load_dotenv

from tools import search_tool, calculator_tool
from math_utils import should_force_calculator, extract_math_expression

from spellchecker import SpellChecker

# Valid modes: "normal", "verbose", "debug"
MODE = "normal"
LLM_TIMEOUT_SECONDS = 20.0
ACTIVE_REQUEST_STOP = threading.Event()

def is_verbose():
    return MODE in ("verbose", "debug")

def is_debug():
    return MODE == "debug"

def reset_stop_signal():
    ACTIVE_REQUEST_STOP.clear()

def request_stop():
    ACTIVE_REQUEST_STOP.set()

def start_wait_counter(label):
    stop_event = threading.Event()

    def run():
        seconds = 0
        while True:
            if stop_event.wait(1):
                break
            if ACTIVE_REQUEST_STOP.is_set():
                break
            seconds += 1
            if is_verbose():
                print(f"[{label} WAIT] {seconds}s")
            else:
                sys.stdout.write("\r" + "waiting" + "." * seconds)
                sys.stdout.flush()

        if not is_verbose() and seconds > 0:
            sys.stdout.write("\r" + " " * (7 + seconds) + "\r\n")
            sys.stdout.flush()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return stop_event

def run_with_hard_timeout(func, label):
    result = {"value": None, "error": None}
    done = threading.Event()

    def run():
        try:
            result["value"] = func()
        except Exception as e:
            result["error"] = e
        finally:
            done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    wait_counter = start_wait_counter(label)
    deadline = time.monotonic() + LLM_TIMEOUT_SECONDS

    while not done.wait(0.1):
        if ACTIVE_REQUEST_STOP.is_set():
            wait_counter.set()
            raise TimeoutError("Cancelled by user.")
        if time.monotonic() >= deadline:
            wait_counter.set()
            raise TimeoutError(f"Operation exceeded {LLM_TIMEOUT_SECONDS:.1f}s.")

    wait_counter.set()

    if result["error"] is not None:
        raise result["error"]

    return result["value"]

load_dotenv()

spell = SpellChecker()
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

def run_self_test():
    reset_stop_signal()

    def record(name, ok, detail):
        status = "PASS" if ok else "FAIL"
        line = f"[SELF-TEST] {name}: {status} - {detail}"
        print(line)

    record("API key present", bool(api_key), str(bool(api_key)))

    try:
        run_with_hard_timeout(
            lambda: socket.getaddrinfo("api.openai.com", 443),
            "SELF-TEST",
        )
        record("DNS resolution", True, "api.openai.com resolved")
    except Exception as e:
        record("DNS resolution", False, f"{type(e).__name__}: {e}")

    try:
        response = run_with_hard_timeout(
            lambda: http_client.get("https://api.openai.com/v1/models"),
            "SELF-TEST",
        )
        record("Raw HTTPS reachability", True, f"HTTP {response.status_code}")
    except Exception as e:
        record("Raw HTTPS reachability", False, f"{type(e).__name__}: {e}")

    try:
        response = run_with_hard_timeout(
            lambda: http_client.get("https://api.openai.com/v1/models", headers=default_headers),
            "SELF-TEST",
        )
        record("Authenticated models request", response.status_code == 200, f"HTTP {response.status_code}")
    except Exception as e:
        record("Authenticated models request", False, f"{type(e).__name__}: {e}")

    try:
        response = run_with_hard_timeout(
            lambda: http_client.get("https://api.openai.com/v1/models", headers=default_headers),
            "SELF-TEST",
        )
        model_ids = {item.get("id") for item in response.json().get("data", []) if isinstance(item, dict)}
        record("Model listed: gpt-5-nano", "gpt-5-nano" in model_ids, "present" if "gpt-5-nano" in model_ids else "not present")
    except Exception as e:
        record("Model listed: gpt-5-nano", False, f"{type(e).__name__}: {e}")

    try:
        response = run_with_hard_timeout(
            lambda: http_client.post(
                "https://api.openai.com/v1/responses",
                headers=default_headers,
                json={"model": "gpt-5-nano", "input": "Reply with exactly: ok"},
            ),
            "SELF-TEST",
        )
        record("Raw responses endpoint", response.status_code == 200, f"HTTP {response.status_code}")
    except Exception as e:
        record("Raw responses endpoint", False, f"{type(e).__name__}: {e}")

    try:
        response = run_with_hard_timeout(lambda: create_response("gpt-5-nano", "Reply with exactly: ok"), "SELF-TEST")
        record("Direct response parsing", True, extract_output_text(response))
    except Exception as e:
        record("Direct response parsing", False, f"{type(e).__name__}: {e}")

    return None

TOOLS = {
    "search_tool": search_tool,
}

SYSTEM_PROMPT = """
You are a tool-using assistant.

Rules:
- Use search_tool when:
- the question is about current events, recent data, or real-time information
- you are unsure of the answer
- the query clearly requires external lookup

- For simple definitions or well-known concepts, you may answer directly with tool = "none"

IMPORTANT:
- When tool = "none", the "input" field MUST contain your actual response to the user
- Never return "input": "none"

Available tools:
1. search_tool(query)

Valid formats:
{"tool": "search_tool", "input": "fastapi"}
{"tool": "none", "input": "Hello! How can I help you?"}

Return exactly one JSON object and nothing else.
Do not include markdown.
Do not include any text before or after the JSON.

Be concise by default. Expand only if the problem requires explanation.
"""
def safe_correct_text(text):
    words = text.split()
    corrected = []

    for word in words:
        # Avoid spell-correcting tokens that are likely literal numeric input.
        if any(char.isdigit() for char in word):
            corrected.append(word)
            continue

        # Preserve operator-bearing tokens so calculator detection still sees the original expression.
        if any(op in word for op in "+-*/"):
            corrected.append(word)
            continue

        fixed = spell.correction(word)
        corrected.append(fixed if fixed else word)

    return " ".join(corrected)

def run_agent(user_input):
    reset_stop_signal()
    corrected_input = safe_correct_text(user_input)
    if is_verbose():
        print(f"[CORRECTED INPUT] {corrected_input}")
    user_input = corrected_input

    # Short-circuit obvious math requests before asking the model to choose a tool.
    if should_force_calculator(user_input):
        expr = extract_math_expression(user_input)
        calc_result = calculator_tool(expr)

        if not str(calc_result).startswith("Error in calculation"):
            if is_verbose():
                print(f"[CALCULATOR] {user_input} -> {expr} -> {calc_result}")
            return calc_result
        else:
            if is_verbose():
                print(f"[CALCULATOR FAILED] {user_input} -> {expr} -> {calc_result}")

            if is_debug():
                return calc_result

            try:
                if is_verbose():
                    print(f"[LLM FALLBACK] Calculator failed, calling model (timeout={LLM_TIMEOUT_SECONDS}s)")
                # If parsing/evaluation fails, fall back to a direct model answer instead of routing through tools.
                response = run_with_hard_timeout(
                    lambda: create_response(
                        "gpt-5-nano",
                        [
                            {
                                "role": "system",
                                "content": "The user's input may be an unusual or poorly phrased math question. Try to answer it directly if possible. If the intent is unclear, say so briefly."
                            },
                            {
                                "role": "user",
                                "content": user_input
                            },
                        ],
                    ),
                    "LLM FALLBACK",
                )
                if is_verbose():
                    print("[LLM FALLBACK DONE] Model returned a fallback answer")
                return extract_output_text(response)
            except Exception as e:
                if is_verbose():
                    print(f"[LLM FALLBACK ERROR TYPE] {type(e).__name__}")
                    print(f"[LLM FALLBACK ERROR] {e}")
                return f"OpenAI API error during math fallback: {type(e).__name__}: {e}"

    if is_verbose():
        print(f"[LLM] {user_input}")

    if is_debug():
        return "DEBUG MODE: LLM call skipped"

    try:
        if is_verbose():
            print(f"[LLM ROUTER] Calling model to choose tool (timeout={LLM_TIMEOUT_SECONDS}s)")
        response = run_with_hard_timeout(
            lambda: create_response(
                "gpt-5-nano",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input},
                ],
            ),
            "LLM ROUTER",
        )

        reply_text = extract_output_text(response)
        if is_verbose():
            print("[LLM ROUTER DONE] Model returned routing decision")
            print(f"[ROUTER RAW] {reply_text}")
    except Exception as e:
        if is_verbose():
            print(f"[LLM ROUTER ERROR TYPE] {type(e).__name__}")
            print(f"[LLM ROUTER ERROR] {e}")
        return f"OpenAI API error during tool routing: {type(e).__name__}: {e}"

    try:
        decision = json.loads(reply_text)
    except json.JSONDecodeError:
        return f"Model returned invalid JSON: {reply_text}"

    tool_name = decision.get("tool")
    tool_input = decision.get("input", "")

    if tool_name in TOOLS:
        if is_verbose():
            print(f"[SEARCH] {tool_input}")
        tool_result = TOOLS[tool_name](tool_input)

        # Turn raw tool output into a user-facing answer in a second model pass.
        if is_verbose():
            print(f"[LLM SYNTHESIS] Calling model to format tool output (timeout={LLM_TIMEOUT_SECONDS}s)")
        response = run_with_hard_timeout(
            lambda: create_response(
                "gpt-5-nano",
                [
                    {
                        "role": "system",
                        "content": "Use the tool result as your primary source. If it is incomplete or unhelpful, you may supplement with general knowledge, but clearly indicate uncertainty."
                    },
                    {
                        "role": "user",
                        "content": f"User asked: {user_input}\nTool returned: {tool_result}"
                    },
                ],
            ),
            "LLM SYNTHESIS",
        )
        if is_verbose():
            print("[LLM SYNTHESIS DONE] Final answer generated")

        return extract_output_text(response)

    if tool_name == "none":
        if tool_input.strip().lower() == "none":
            return "I'm not sure how to respond to that."
        return tool_input
