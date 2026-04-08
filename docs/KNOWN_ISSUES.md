# Known Issues

This file tracks active bugs, quirks, and things that should be re-verified after changes.

## Active

- Request stop is a soft local cancel. It stops waiting in the CLI, but it does not guarantee the in-flight HTTP request is fully aborted server-side.
- The CLI control flow now depends on background threads and timed waits. Any future refactor touching request execution, waiting output, or quit behavior should re-test those paths carefully.
- Runtime behavior now depends on the interaction between `mode`, `output`, and `connection`; CLI resolution changes should be re-tested carefully.
- `agent.py` currently holds most provider, timeout, wait-status, and orchestration logic; keep future refactors narrow so stability does not regress.
- Ollama availability depends on the local environment; provider behavior may differ between the development machine and the sandboxed verification environment.
- The current local model can still violate the desired factual/current lookup policy by answering directly instead of selecting search.
- Calculator parse failure still uses a direct LLM fallback instead of a dedicated math/search API path.
- Very small `--timeout` values can still fail simply because neither provider gets enough useful budget.

## Re-Test After Relevant Changes

- `py main.py --self-test`
- `py main.py --mode debug`
- `py main.py --mode debug --connection api`
- `py main.py --mode normal --output verbose`
- `py main.py --mode normal --connection local`
- normal-mode `waiting...` should be replaced cleanly by a completion or failure line
- `py scripts/smoke_test.py`
- `py scripts/smoke_test.py --verbose`
- `py scripts/smoke_test.py` should exit cleanly without a Python shutdown error
- `py scripts/smoke_test.py` should also keep passing the natural-language calculator case
- `2+2` should stay on the calculator path and return `4`
- `2++` should fail calculator parsing and fall back to the LLM without hanging when API connection is enabled
- `2++` in local connection mode should return the calculator error directly
- `s` should stop a running request and return to the prompt
- `q` during a running request should quit the program
- `q`, `quit`, and `exit` at the prompt should quit cleanly
- `py main.py --provider openai`
- `py main.py --provider ollama`
- `py main.py --provider auto`
- `py main.py --timeout 30`
- `py main.py --output verbose`
- test local-only, OpenAI-only, and local-first fallback behavior separately
- confirm verbose terminal output stays concise while raw router/provider payloads remain in `logs/latest.log`
- verify default `auto` fallback when Ollama is slow or unavailable

## Resolved Recently

- OpenAI SDK `responses.create(...)` hanging in this environment
  - Replaced with direct `httpx` calls to `POST /v1/responses`
- LLM wait could continue far past the intended timeout
  - Added an app-level hard timeout wrapper around request execution
