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
    LLMProviderError,
    api_key,
    default_headers,
    generate_text,
    http_client,
    set_timeout_seconds as set_llm_client_timeout_seconds,
)

from spellchecker import SpellChecker

MODE = "normal"
OUTPUT = "friendly"
CONNECTION = "api"
PROVIDER = "openai"
LLM_TIMEOUT_SECONDS = 45.0
LLM_TIMEOUT_GRACE_SECONDS = 0.5
ACTIVE_REQUEST_STOP = threading.Event()
LOG_HANDLES = []
SELF_TEST_ACTIVE = False
SMOKE_TEST_ACTIVE = False
LAST_LLM_ELAPSED = None

def configure_runtime(mode, output, connection, provider, log_paths, timeout_seconds=None):
    global MODE, OUTPUT, CONNECTION, PROVIDER, LLM_TIMEOUT_SECONDS

    MODE = mode
    OUTPUT = output
    CONNECTION = connection
    PROVIDER = provider
    if timeout_seconds is not None:
        LLM_TIMEOUT_SECONDS = float(timeout_seconds)
        set_llm_client_timeout_seconds(LLM_TIMEOUT_SECONDS)

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


def shared_log(message, *, stdout=True, stdout_message=None):
    if stdout:
        print(stdout_message if stdout_message is not None else message)
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


def get_provider():
    return PROVIDER


def get_provider_model():
    if get_provider() == "openai":
        return LLM_MODEL
    return None


def log_debug(message):
    if is_verbose_output():
        shared_log(message)


def log_llm_start(label):
    if is_debug_mode() or is_verbose_output():
        if is_debug_mode():
            shared_log(f"{label} (timeout={LLM_TIMEOUT_SECONDS:.1f}s)")


def summarize_detail(detail, max_length=160):
    text = str(detail).strip()
    if not text:
        return text

    first_line = text.splitlines()[0].strip()
    if len(first_line) <= max_length:
        return first_line
    return first_line[: max_length - 3].rstrip() + "..."

def extract_router_json(text):
    if not isinstance(text, str):
        raise json.JSONDecodeError("Router output is not a string", "", 0)

    try:
        return json.loads(text)
    except json.JSONDecodeError as first_error:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        raise first_error

def is_unhelpful_direct_answer(user_input, answer_text):
    if not isinstance(answer_text, str):
        return True

    normalized_answer = answer_text.strip()
    if not normalized_answer:
        return True

    return normalized_answer.casefold() == user_input.strip().casefold()


def log_llm_result(result):
    global LAST_LLM_ELAPSED
    if not is_verbose_output() or not isinstance(result, dict):
        return

    provider = result.get("provider", "unknown")
    model = result.get("model", "unknown")
    attempted_provider = result.get("attempted_provider", provider)
    fallback_used = bool(result.get("fallback_used"))
    fallback_reason = result.get("fallback_reason")
    attempts = result.get("attempts") or []

    if attempts:
        for attempt in attempts[:-1]:
            elapsed = attempt.get("elapsed_seconds")
            elapsed_text = f"{elapsed:.2f}s" if isinstance(elapsed, (int, float)) else "unknown"
            reason = summarize_detail(attempt.get("reason", "failed"))
            shared_log(
                f"[LLM ATTEMPT] provider={attempt.get('provider')} model={attempt.get('model')} status={attempt.get('status')} elapsed={elapsed_text} reason={reason}"
            )

        final_attempt = attempts[-1]
        elapsed = final_attempt.get("elapsed_seconds")
        elapsed_text = f"{elapsed:.2f}s" if isinstance(elapsed, (int, float)) else (
            f"{LAST_LLM_ELAPSED:.2f}s" if LAST_LLM_ELAPSED is not None else "unknown"
        )
        shared_log(
            f"[LLM SUCCESS] completed={elapsed_text} provider={provider} model={model}"
        )
    else:
        elapsed_text = f"{LAST_LLM_ELAPSED:.2f}s" if LAST_LLM_ELAPSED is not None else "unknown"
        shared_log(f"[LLM SUCCESS] completed={elapsed_text} provider={provider} model={model}")

    if fallback_used and fallback_reason and not attempts:
        shared_log(f"[LLM ATTEMPT] provider={attempted_provider} status=failed reason={summarize_detail(fallback_reason)}")
    raw_response = result.get("raw_response")
    if raw_response is not None and provider == "ollama":
        shared_log(f"[OLLAMA RAW] {summarize_detail(ascii(raw_response), max_length=400)}", stdout=False)
    LAST_LLM_ELAPSED = None


def is_rate_limit_error(error):
    return isinstance(error, LLMProviderError) and "rate_limit_exceeded" in str(error)


def llm_status_label():
    return f"[LLM:{get_provider()}]"


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
    global LAST_LLM_ELAPSED
    usage_summary = format_usage_summary(response_data) if isinstance(response_data, dict) else None
    LAST_LLM_ELAPSED = elapsed_seconds
    if is_debug_mode():
        timeout_text = f"(timeout={LLM_TIMEOUT_SECONDS:.1f}s) "
        line = f"{label} {timeout_text}completed in {elapsed_seconds:.2f}s"
        if usage_summary:
            suffix = "usage" if is_debug_mode() else "tokens"
            line += f" | {suffix}: {usage_summary}"
        return line

    return None


def format_failure_status(label, elapsed_seconds):
    if is_debug_mode() or is_verbose_output():
        return f"[FAILED] {label} (timeout={LLM_TIMEOUT_SECONDS:.1f}s) after {elapsed_seconds:.2f}s"
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
            if SELF_TEST_ACTIVE or SMOKE_TEST_ACTIVE:
                continue
            if is_verbose_output():
                sys.stdout.write("\r" + f"{label} waiting {state['seconds']}s (timeout={LLM_TIMEOUT_SECONDS:.1f}s)")
                sys.stdout.flush()
            else:
                sys.stdout.write("\r" + "." * state["seconds"])
                sys.stdout.flush()

    thread = threading.Thread(target=run)
    thread.start()

    def stop(final_message=None, stdout_message=None):
        stop_event.set()
        thread.join()

        if SELF_TEST_ACTIVE or SMOKE_TEST_ACTIVE:
            if final_message:
                for handle in LOG_HANDLES:
                    handle.write(final_message + "\n")
                    handle.flush()
            elif state["seconds"] > 0:
                sys.stdout.write("\r" + " " * state["seconds"] + "\r")
                sys.stdout.flush()
            return

        if is_verbose_output():
            if state["seconds"] > 0:
                clear_width = len(f"{label} waiting {state['seconds']}s (timeout={LLM_TIMEOUT_SECONDS:.1f}s)")
                sys.stdout.write("\r" + " " * clear_width + "\r")
                sys.stdout.flush()
            if final_message:
                shared_log(
                    final_message,
                    stdout=stdout_message is not False,
                    stdout_message=None if stdout_message is False else stdout_message,
                )
            return

        if state["seconds"] > 0:
            if final_message:
                if stdout_message is not False:
                    terminal_message = final_message if stdout_message is None else stdout_message
                    sys.stdout.write("\r" + terminal_message + "\n")
            else:
                sys.stdout.write("\r" + " " * state["seconds"] + "\r")
            sys.stdout.flush()
        elif final_message and stdout_message is not False:
            shared_log(final_message, stdout_message=stdout_message)

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
    deadline = time.monotonic() + LLM_TIMEOUT_SECONDS + LLM_TIMEOUT_GRACE_SECONDS
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
        completion_status = locals().get("completion_status") or ""
        suppress_stdout = (SELF_TEST_ACTIVE or SMOKE_TEST_ACTIVE) and completion_status.startswith("[FAILED]")
        stop_wait_counter(
            locals().get("completion_status"),
            stdout_message=False if suppress_stdout else None,
        )
        if done.is_set():
            thread.join()


def set_smoke_test_active(active):
    global SMOKE_TEST_ACTIVE
    SMOKE_TEST_ACTIVE = active

spell = SpellChecker()
def run_self_test():
    global SELF_TEST_ACTIVE
    reset_stop_signal()
    SELF_TEST_ACTIVE = True

    def record(name, ok, detail, *, status=None):
        status = status or ("PASS" if ok else "FAIL")
        detail_text = str(detail)
        line = f"[{status}] {name}: {detail_text}"
        display_name = name.split(") ", 1)[1] if name.startswith("(") and ") " in name else name
        summary_line = f"[{status}] {display_name}"
        if status == "PASS":
            summary_line = f"[{status}] {display_name}: {summarize_detail(detail_text)}"
        if is_debug_mode():
            log_debug(summary_line)
            if summary_line != line:
                shared_log(line, stdout=False)
        else:
            shared_log(line, stdout_message=summary_line)

    def record_timed(name, ok, detail, elapsed_seconds, *, status=None):
        status = status or ("PASS" if ok else "FAIL")
        detail_text = str(detail)
        timed_name = f"({elapsed_seconds:.2f}s) {name}"
        record(timed_name, ok, detail_text, status=status)

    def timed(func):
        started_at = time.monotonic()
        try:
            value = func()
            return value, time.monotonic() - started_at
        except Exception as e:
            setattr(e, "_elapsed_seconds", time.monotonic() - started_at)
            raise
    try:
        record_timed("API key present", bool(api_key), str(bool(api_key)), 0.0)

        try:
            _, elapsed = timed(
                lambda: run_with_hard_timeout(
                    lambda: socket.getaddrinfo("api.openai.com", 443),
                    "SELF-TEST",
                )
            )
            record_timed("DNS resolution", True, "api.openai.com resolved", elapsed)
        except Exception as e:
            record_timed("DNS resolution", False, f"{type(e).__name__}: {e}", getattr(e, "_elapsed_seconds", 0.0))

        try:
            response, elapsed = timed(
                lambda: run_with_hard_timeout(
                    lambda: http_client.get("https://api.openai.com/v1/models"),
                    "SELF-TEST",
                )
            )
            record_timed("Raw HTTPS reachability", True, f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            record_timed("Raw HTTPS reachability", False, f"{type(e).__name__}: {e}", getattr(e, "_elapsed_seconds", 0.0))

        try:
            response, elapsed = timed(
                lambda: run_with_hard_timeout(
                    lambda: http_client.get("https://api.openai.com/v1/models", headers=default_headers),
                    "SELF-TEST",
                )
            )
            record_timed(
                "Authenticated models request",
                response.status_code == 200,
                f"HTTP {response.status_code}",
                elapsed,
            )
        except Exception as e:
            record_timed("Authenticated models request", False, f"{type(e).__name__}: {e}", getattr(e, "_elapsed_seconds", 0.0))

        try:
            response, elapsed = timed(
                lambda: run_with_hard_timeout(
                    lambda: http_client.get("https://api.openai.com/v1/models", headers=default_headers),
                    "SELF-TEST",
                )
            )
            model_ids = {item.get("id") for item in response.json().get("data", []) if isinstance(item, dict)}
            record_timed(
                "Model listed: gpt-5-nano",
                "gpt-5-nano" in model_ids,
                "present" if "gpt-5-nano" in model_ids else "not present",
                elapsed,
            )
        except Exception as e:
            record_timed("Model listed: gpt-5-nano", False, f"{type(e).__name__}: {e}", getattr(e, "_elapsed_seconds", 0.0))

        try:
            response, elapsed = timed(
                lambda: run_with_hard_timeout(
                    lambda: http_client.post(
                        "https://api.openai.com/v1/responses",
                        headers=default_headers,
                        json={"model": "gpt-5-nano", "input": "Reply with exactly: ok"},
                    ),
                    "SELF-TEST",
                )
            )
            record_timed("Raw responses endpoint", response.status_code == 200, f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            record_timed("Raw responses endpoint", False, f"{type(e).__name__}: {e}", getattr(e, "_elapsed_seconds", 0.0))

        try:
            result, elapsed = timed(
                lambda: run_with_hard_timeout(
                    lambda: generate_text(
                        "Reply with exactly: ok",
                        provider=get_provider(),
                        connection=CONNECTION,
                        model="gpt-5-nano",
                        reasoning_effort="low",
                    ),
                    "SELF-TEST",
                )
            )
            log_llm_result(result)
            record_timed("Direct response parsing", True, result["text"], elapsed)
            detail = f"provider={result['provider']} model={result['model']} text={result['text']!r}"
            record_timed("Provider generate: openai", True, detail, elapsed)
        except Exception as e:
            elapsed = getattr(e, "_elapsed_seconds", 0.0)
            record_timed("Direct response parsing", False, f"{type(e).__name__}: {e}", elapsed)
            record_timed("Provider generate: openai", False, f"{type(e).__name__}: {e}", elapsed)

        try:
            result, elapsed = timed(
                lambda: run_with_hard_timeout(
                    lambda: generate_text(
                        "Reply with exactly: ok",
                        provider="ollama",
                        connection="local",
                        max_output_tokens=64,
                    ),
                    "SELF-TEST",
                )
            )
            log_llm_result(result)
            detail = f"provider={result['provider']} model={result['model']} text={result['text']!r}"
            record_timed("Provider generate: ollama", True, detail, elapsed)
        except Exception as e:
            record_timed("Provider generate: ollama", False, f"{type(e).__name__}: {e}", getattr(e, "_elapsed_seconds", 0.0))

        try:
            result, elapsed = timed(
                lambda: run_with_hard_timeout(
                    lambda: generate_text(
                        "Reply with exactly: ok",
                        provider="auto",
                        connection="api",
                        reasoning_effort="low",
                    ),
                    "SELF-TEST",
                )
            )
            log_llm_result(result)
            detail = (
                f"answered={result['provider']} "
                f"attempted={result.get('attempted_provider')} "
                f"fallback={result.get('fallback_used')} "
                f"text={result['text']!r}"
            )
            if result.get("fallback_used") and result.get("fallback_reason"):
                detail += f" reason={result['fallback_reason']}"
            record_timed("Provider generate: auto", True, detail, elapsed)
        except Exception as e:
            status = "SKIP" if is_rate_limit_error(e) else None
            record_timed("Provider generate: auto", False, f"{type(e).__name__}: {e}", getattr(e, "_elapsed_seconds", 0.0), status=status)

        return None
    finally:
        SELF_TEST_ACTIVE = False

TOOLS = {
    "search_tool": search_tool,
}

ROUTER_SYSTEM_PROMPT = (
    'Return ONLY JSON: {"tool":"none|search_tool","input":"","answer":""}. '
    'If tool="none", input must be empty and answer must contain the brief user-facing reply. '
    'If tool="search_tool", input must be a short search query matching the user request and answer must be empty. '
    'Use tool="none" for greetings, jokes, vague short inputs, and normal conversation. '
    'Use tool="search_tool" only for factual or external information that should be looked up. '
    'Do not invent details or turn a vague prompt into a different question. JSON only.'
)
DIRECT_ANSWER_SYSTEM_PROMPT = (
    "Answer directly. Respond in the shortest correct answer. If unclear, say so briefly."
)
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

        prefix_end = 0
        while prefix_end < len(word) and not word[prefix_end].isalnum():
            prefix_end += 1

        suffix_start = len(word)
        while suffix_start > prefix_end and not word[suffix_start - 1].isalnum():
            suffix_start -= 1

        prefix = word[:prefix_end]
        core = word[prefix_end:suffix_start]
        suffix = word[suffix_start:]

        if not core:
            corrected.append(word)
            continue

        fixed = spell.correction(core)
        corrected_core = fixed if fixed else core
        corrected.append(prefix + corrected_core + suffix)

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
                log_llm_start(llm_status_label())
                # If parsing/evaluation fails, fall back to a direct model answer instead of routing through tools.
                response = run_with_hard_timeout(
                    lambda: generate_text(
                        [
                            {
                                "role": "system",
                                "content": DIRECT_ANSWER_SYSTEM_PROMPT
                            },
                            {
                                "role": "user",
                                "content": user_input
                            },
                        ],
                        provider=get_provider(),
                        connection=CONNECTION,
                        model=get_provider_model(),
                        reasoning_effort="low",
                    ),
                    llm_status_label(),
                )
                log_llm_result(response)
                return response["text"]
            except Exception as e:
                shared_log(f"[LLM FALLBACK ERROR] {type(e).__name__}: {e}", stdout=False)
                return f"LLM error during math fallback: {type(e).__name__}: {e}"

    log_debug(f"[LLM INPUT] {user_input}")

    if is_local_connection():
        return "LLM call skipped: local connection mode"

    try:
        log_llm_start(llm_status_label())
        response = run_with_hard_timeout(
            lambda: generate_text(
                [
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_input},
                ],
                provider=get_provider(),
                connection=CONNECTION,
                model=get_provider_model(),
                reasoning_effort="low",
            ),
            llm_status_label(),
        )

        log_llm_result(response)
        reply_text = response["text"]
        shared_log(f"[ROUTER RAW] {reply_text}", stdout=False)
    except Exception as e:
        shared_log(f"[LLM ROUTER ERROR] {type(e).__name__}: {e}", stdout=False)
        return f"LLM error during tool routing: {type(e).__name__}: {e}"

    try:
        decision = extract_router_json(reply_text)
    except json.JSONDecodeError:
        return f"Model returned invalid JSON: {reply_text}"

    tool_name = decision.get("tool")
    tool_input = decision.get("input", "")
    direct_answer = decision.get("answer", "")
    router_line = f"[LLM ROUTER] tool={tool_name!r} input={tool_input!r} answer={direct_answer!r}"
    if tool_name == "none":
        shared_log(router_line, stdout=False)
    else:
        log_debug(router_line)

    if tool_name in TOOLS:
        log_debug(f"[SEARCH] {tool_input}")
        tool_result = TOOLS[tool_name](tool_input)
        shared_log(f"[LLM OUTPUT] {tool_result}", stdout=False)
        return tool_result

    if tool_name == "none":
        if is_unhelpful_direct_answer(user_input, direct_answer):
            return "I'm not sure how to respond to that."
        shared_log(f"[LLM OUTPUT] {direct_answer}", stdout=False)
        return direct_answer
