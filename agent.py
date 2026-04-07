import json
import socket
import sys
import threading
import time
from pathlib import Path

from tools import search_tool, calculator_tool
from math_utils import should_force_calculator, extract_math_expression
from llm_client import (
    LLM_MODEL,
    api_key,
    create_response,
    default_headers,
    extract_output_text,
    http_client,
)

from spellchecker import SpellChecker

MODE = "normal"
OUTPUT = "friendly"
CONNECTION = "api"
LLM_TIMEOUT_SECONDS = 20.0
ACTIVE_REQUEST_STOP = threading.Event()
LOG_HANDLES = []

def configure_runtime(mode, output, connection, log_paths):
    global MODE, OUTPUT, CONNECTION

    MODE = mode
    OUTPUT = output
    CONNECTION = connection

    close_runtime()
    for path in log_paths:
        log_path = Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_mode = "w" if log_path.name == "latest.log" else "a"
        LOG_HANDLES.append(log_path.open(file_mode, encoding="utf-8"))


def close_runtime():
    global LOG_HANDLES

    for handle in LOG_HANDLES:
        handle.close()
    LOG_HANDLES = []


def shared_log(message, *, stdout=True):
    if stdout:
        print(message)
    for handle in LOG_HANDLES:
        handle.write(message + "\n")
        handle.flush()


def is_normal_mode():
    return MODE == "normal"


def is_debug_mode():
    return MODE == "debug"


def is_friendly_output():
    return OUTPUT == "friendly"


def is_verbose_output():
    return OUTPUT == "verbose"


def is_api_connection():
    return CONNECTION == "api"


def is_local_connection():
    return CONNECTION == "local"


def log_debug(message):
    if is_verbose_output():
        shared_log(message)


def llm_status_label():
    return f"[LLM:{LLM_MODEL}]"

def format_usage_summary(response_data):
    usage = response_data.get("usage")
    if not isinstance(usage, dict):
        return None

    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")

    parts = []
    if isinstance(input_tokens, int):
        parts.append(f"{input_tokens} in")
    if isinstance(output_tokens, int):
        parts.append(f"{output_tokens} out")

    return " • ".join(parts) if parts else None

def print_completion_status(label, elapsed_seconds, response_data=None):
    usage_summary = format_usage_summary(response_data) if isinstance(response_data, dict) else None
    model_prefix = f"[{LLM_MODEL}] "

    if is_debug_mode():
        line = f"{model_prefix}[DONE] {label} completed in {elapsed_seconds:.2f}s"
        if usage_summary:
            line += f" | usage: {usage_summary}"
        shared_log(line)
        return

    if is_verbose_output():
        line = f"{model_prefix}[DONE] {label} completed in {elapsed_seconds:.2f}s"
        if usage_summary:
            line += f" | tokens: {usage_summary}"
        shared_log(line)
        return

    line = f"{model_prefix}{elapsed_seconds:.1f}s"
    if usage_summary:
        line += f" • {usage_summary}"
    shared_log(line)


def format_completion_status(label, elapsed_seconds, response_data=None):
    usage_summary = format_usage_summary(response_data) if isinstance(response_data, dict) else None
    model_prefix = f"[{LLM_MODEL}] "

    if is_debug_mode():
        line = f"{label} completed in {elapsed_seconds:.2f}s"
        if usage_summary:
            line += f" | usage: {usage_summary}"
        return line

    if is_verbose_output():
        line = f"{label} completed in {elapsed_seconds:.2f}s"
        if usage_summary:
            line += f" | tokens: {usage_summary}"
        return line

    return None


def format_failure_status(label, elapsed_seconds):
    if is_debug_mode() or is_verbose_output():
        return f"[FAILED] {label} after {elapsed_seconds:.2f}s"
    return f"failed in {elapsed_seconds:.1f}s"

def reset_stop_signal():
    ACTIVE_REQUEST_STOP.clear()

def request_stop():
    ACTIVE_REQUEST_STOP.set()

def start_wait_counter(label):
    stop_event = threading.Event()
    state = {"seconds": 0}

    def run():
        while True:
            if stop_event.wait(1):
                break
            if ACTIVE_REQUEST_STOP.is_set():
                break
            state["seconds"] += 1
            if is_verbose_output():
                shared_log(f"{label} WAIT {state['seconds']}s")
            else:
                sys.stdout.write("\r" + "waiting" + "." * state["seconds"])
                sys.stdout.flush()

    thread = threading.Thread(target=run)
    thread.start()

    def stop(final_message=None):
        stop_event.set()
        thread.join()

        if is_verbose_output():
            if final_message:
                shared_log(final_message)
            return

        if state["seconds"] > 0:
            if final_message:
                sys.stdout.write("\r" + final_message + "\n")
            else:
                sys.stdout.write("\r" + " " * (7 + state["seconds"]) + "\r")
            sys.stdout.flush()
        elif final_message:
            shared_log(final_message)

        if final_message:
            for handle in LOG_HANDLES:
                handle.write(final_message + "\n")
                handle.flush()

    return stop

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

    stop_wait_counter = start_wait_counter(label)
    deadline = time.monotonic() + LLM_TIMEOUT_SECONDS
    started_at = time.monotonic()

    try:
        while not done.wait(0.1):
            if ACTIVE_REQUEST_STOP.is_set():
                raise TimeoutError("Cancelled by user.")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Operation exceeded {LLM_TIMEOUT_SECONDS:.1f}s.")

        if result["error"] is not None:
            raise result["error"]

        elapsed_seconds = time.monotonic() - started_at
        completion_status = format_completion_status(label, elapsed_seconds, result["value"])
        return result["value"]
    except Exception:
        completion_status = format_failure_status(label, time.monotonic() - started_at)
        if is_debug_mode():
            log_debug(f"[TIMER] {label} failed after {time.monotonic() - started_at:.2f}s")
        raise
    finally:
        stop_wait_counter(locals().get("completion_status"))
        if done.is_set():
            thread.join()

spell = SpellChecker()
def run_self_test():
    reset_stop_signal()

    def record(name, ok, detail):
        status = "PASS" if ok else "FAIL"
        line = f"[{status}] {name}: {detail}"
        if is_debug_mode():
            log_debug(line)
        else:
            shared_log(line)

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

Respond as concisely as possible. Prefer one short sentence unless more detail is necessary.
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
    if corrected_input != user_input:
        log_debug(f"[CORRECTED INPUT] {corrected_input}")
    user_input = corrected_input

    # Short-circuit obvious math requests before asking the model to choose a tool.
    if should_force_calculator(user_input):
        expr = extract_math_expression(user_input)
        calc_result = calculator_tool(expr)

        if not str(calc_result).startswith("Error in calculation"):
            log_debug(f"[CALCULATOR] {user_input} -> {expr} -> {calc_result}")
            return calc_result
        else:
            log_debug(f"[CALCULATOR FAILED] {user_input} -> {expr}")

            if is_local_connection():
                return calc_result

            try:
                log_debug(f"{llm_status_label()} (timeout={LLM_TIMEOUT_SECONDS}s)")
                # If parsing/evaluation fails, fall back to a direct model answer instead of routing through tools.
                response = run_with_hard_timeout(
                    lambda: create_response(
                        LLM_MODEL,
                        [
                            {
                                "role": "system",
                                "content": "The user's input may be unusual or poorly phrased. Answer as directly as possible in one short sentence. If the intent is unclear, say so briefly."
                            },
                            {
                                "role": "user",
                                "content": user_input
                            },
                        ],
                    ),
                    llm_status_label(),
                )
                return extract_output_text(response)
            except Exception as e:
                log_debug(f"[LLM FALLBACK ERROR TYPE] {type(e).__name__}")
                log_debug(f"[LLM FALLBACK ERROR] {e}")
                return f"OpenAI API error during math fallback: {type(e).__name__}: {e}"

    log_debug(f"[LLM] {user_input}")

    if is_local_connection():
        return "LLM call skipped: local connection mode"

    try:
        log_debug(f"{llm_status_label()} (timeout={LLM_TIMEOUT_SECONDS}s)")
        response = run_with_hard_timeout(
            lambda: create_response(
                LLM_MODEL,
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input},
                ],
            ),
            llm_status_label(),
        )

        reply_text = extract_output_text(response)
        log_debug(f"[ROUTER RAW] {reply_text}")
    except Exception as e:
        log_debug(f"[LLM ROUTER ERROR TYPE] {type(e).__name__}")
        log_debug(f"[LLM ROUTER ERROR] {e}")
        return f"OpenAI API error during tool routing: {type(e).__name__}: {e}"

    try:
        decision = json.loads(reply_text)
    except json.JSONDecodeError:
        return f"Model returned invalid JSON: {reply_text}"

    tool_name = decision.get("tool")
    tool_input = decision.get("input", "")

    if tool_name in TOOLS:
        log_debug(f"[SEARCH] {tool_input}")
        tool_result = TOOLS[tool_name](tool_input)

        # Turn raw tool output into a user-facing answer in a second model pass.
        log_debug(f"{llm_status_label()} (timeout={LLM_TIMEOUT_SECONDS}s)")
        response = run_with_hard_timeout(
            lambda: create_response(
                LLM_MODEL,
                [
                    {
                        "role": "system",
                        "content": "Use the tool result as your primary source and answer in one short sentence when possible. If needed, briefly indicate uncertainty."
                    },
                    {
                        "role": "user",
                        "content": f"User asked: {user_input}\nTool returned: {tool_result}"
                    },
                ],
            ),
            llm_status_label(),
        )

        return extract_output_text(response)

    if tool_name == "none":
        if tool_input.strip().lower() == "none":
            return "I'm not sure how to respond to that."
        return tool_input
