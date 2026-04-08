import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent
from llm_client import LLMProviderError, generate_text


def summarize_detail(detail, max_length=120):
    text = str(detail).strip()
    if not text:
        return text
    first_line = text.splitlines()[0].strip()
    if len(first_line) <= max_length:
        return first_line
    return first_line[: max_length - 3].rstrip() + "..."


def report(status, name, detail, *, summary_detail=None):
    full_line = f"[{status}] {name}: {detail}"
    if summary_detail is None:
        summary_line = f"[{status}] {name}"
    else:
        summary_line = f"[{status}] {name}: {summary_detail}"
    agent.shared_log(full_line, stdout_message=summary_line)


def check(name, condition, detail):
    status = "PASS" if condition else "FAIL"
    summary_detail = summarize_detail(detail) if condition else None
    report(status, name, detail, summary_detail=summary_detail)
    return condition


def summarize_skip_detail(detail):
    text = str(detail)
    lowered = text.lower()
    if "rate_limit_exceeded" in lowered or "rate limit reached" in lowered:
        return "rate limited"
    if "providerunavailableerror" in lowered or "ollama unavailable" in lowered:
        return "provider unavailable"
    if "timed out" in lowered or "timeout" in lowered:
        return "timed out"
    return summarize_detail(detail)


def skip(name, detail):
    report("SKIP", name, detail, summary_detail=summarize_skip_detail(detail))


def is_rate_limit_error(error):
    return isinstance(error, LLMProviderError) and "rate_limit_exceeded" in str(error)


def should_show_detail():
    return "--verbose" in sys.argv


def main():
    agent.set_smoke_test_active(True)
    agent.configure_runtime(
        mode="normal",
        output="friendly",
        connection="api",
        provider="openai",
        log_paths=[Path("logs/latest.log")],
    )

    passed = 0
    total = 0
    skipped = 0

    try:
        total += 1
        result = agent.run_agent("2+2")
        detail = repr(result) if should_show_detail() else str(result).strip()
        if check("calculator", str(result).strip() == "4", detail):
            passed += 1

        total += 1
        result = agent.run_agent("twenty-two plus five")
        detail = repr(result) if should_show_detail() else str(result).strip()
        if check("natural language calculator", str(result).strip() == "27", detail):
            passed += 1

        total += 1
        result = agent.run_agent("2++")
        ok = (
            isinstance(result, str)
            and bool(result.strip())
            and "OpenAI API error" not in result
            and "TimeoutError" not in result
        )
        detail = repr(result) if should_show_detail() else ("ok" if ok else repr(result))
        if check("math fallback", ok, detail):
            passed += 1

        total += 1
        result = agent.run_agent("hello")
        text = str(result).strip()
        ok = (
            isinstance(result, str)
            and bool(text)
            and "OpenAI API error" not in text
            and "Model returned invalid JSON" not in text
            and "LLM call skipped" not in text
            and "TimeoutError" not in text
        )
        detail = repr(result) if should_show_detail() else ("ok" if ok else repr(result))
        if check("basic llm response", ok, detail):
            passed += 1

        total += 1
        try:
            result = generate_text("Reply with exactly: ok", provider="openai", connection="api")
            ok = result["provider"] == "openai" and result["text"].strip().lower() == "ok" and not result["fallback_used"]
            detail = repr(result) if should_show_detail() else ("ok" if ok else repr(result))
            if check("openai provider", ok, detail):
                passed += 1
        except Exception as e:
            if is_rate_limit_error(e):
                skip("openai provider", f"{type(e).__name__}: {e}")
                skipped += 1
                total -= 1
            else:
                raise

        ollama_available = False
        total += 1
        try:
            result = generate_text("Reply with exactly: ok", provider="ollama", connection="local")
            ollama_available = True
            ok = result["provider"] == "ollama" and bool(result["text"].strip()) and not result["fallback_used"]
            detail = repr(result) if should_show_detail() else ("ok" if ok else repr(result))
            if check("ollama provider", ok, detail):
                passed += 1
        except Exception as e:
            skip("ollama provider", f"{type(e).__name__}: {e}")
            skipped += 1
            total -= 1

        total += 1
        try:
            result = generate_text("Reply with exactly: ok", provider="auto", connection="api")
            if ollama_available:
                ok = result["provider"] == "ollama" and not result["fallback_used"]
            else:
                ok = (
                    result["provider"] == "openai"
                    and result["fallback_used"]
                    and result["attempted_provider"] == "ollama"
                    and bool(result.get("fallback_reason"))
                )
            detail = repr(result) if should_show_detail() else ("ok" if ok else repr(result))
            if check("auto provider", ok, detail):
                passed += 1
        except Exception as e:
            if is_rate_limit_error(e):
                skip("auto provider", f"{type(e).__name__}: {e}")
                skipped += 1
                total -= 1
            else:
                raise

        failed = total - passed
        summary = f"{passed}/{total} checks passed"
        if skipped:
            summary += f", {skipped} skipped"
        if failed:
            summary += f", {failed} failed"
        print(f"\n{summary}")

        if failed != 0:
            raise SystemExit(1)
    finally:
        agent.set_smoke_test_active(False)
        agent.close_runtime()


if __name__ == "__main__":
    main()
