import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent
from llm_client import generate_text


def check(name, condition, detail):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}: {detail}")
    return condition


def skip(name, detail):
    print(f"[SKIP] {name}: {detail}")


def should_show_detail():
    return "--verbose" in sys.argv


def main():
    agent.configure_runtime(
        mode="normal",
        output="friendly",
        connection="api",
        provider="openai",
        log_paths=[Path("logs/latest.log")],
    )

    passed = 0
    total = 0

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
        ok = isinstance(result, str) and bool(result.strip())
        detail = repr(result) if should_show_detail() else ("ok" if ok else repr(result))
        if check("basic llm response", ok, detail):
            passed += 1

        total += 1
        result = generate_text("Reply with exactly: ok", provider="openai", connection="api")
        ok = result["provider"] == "openai" and result["text"].strip().lower() == "ok" and not result["fallback_used"]
        detail = repr(result) if should_show_detail() else ("ok" if ok else repr(result))
        if check("openai provider", ok, detail):
            passed += 1

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
            total -= 1
            skip("ollama provider", f"{type(e).__name__}: {e}")

        total += 1
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

        print(f"\n{passed}/{total} checks passed")

        if passed != total:
            raise SystemExit(1)
    finally:
        agent.close_runtime()


if __name__ == "__main__":
    main()
