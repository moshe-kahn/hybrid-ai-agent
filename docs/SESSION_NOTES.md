# Session Notes

Use this file for dated summaries of meaningful work completed during a session. Keep entries short and high-signal.

## 2026-04-04

- Added CLI mode selection and then split runtime configuration into `mode`, `output`, and `connection`.
- Added interactive request controls:
  - `s` stops waiting and returns to the prompt
  - `q` quits immediately during an in-flight request
- Added `--self-test` with progressive checks for key presence, DNS, HTTPS reachability, authenticated model access, model availability, and response generation.
- Diagnosed that the OpenAI SDK response path was hanging in this environment even though raw API access worked.
- Replaced SDK response calls with direct `httpx` requests to `/v1/responses`.
- Added app-level timeout handling around LLM calls.
- Added `scripts/smoke_test.py` for a minimal automation-friendly smoke test.
- Fixed wait-thread cleanup so the process does not crash on shutdown after smoke tests.
- Centralized debug output behind a small helper and added timing output for timed request paths in debug mode.
- Expanded smoke coverage with an additional stable natural-language calculator check.
- Added concise completion summaries for timed LLM calls, including elapsed time and token usage when available.
- Added an optional `--verbose` mode to the smoke test while keeping default output concise.
- Split CLI runtime configuration into `mode`, `output`, and `connection`.
- Added lightweight shared run logging with automatic `logs/latest.log` creation and optional extra log-file append support.
- Refined normal-mode wait UX so `waiting...` finalizes into a clean completion/failure line.
- Kept friendly completion summaries minimal and limited model/token detail to verbose/debug output.
- Removed successful completion summaries from friendly output so it goes straight from waiting to the answer.
- Shortened verbose/debug calculator failure logs to avoid duplicate error text.
- Simplified verbose/debug LLM status logging to `LLM:<model>` and removed redundant completion follow-up lines.
- Switched verbose/debug LLM labels to bracketed form and suppressed unchanged corrected-input logs.
- Fixed verbose/debug wait-line formatting to avoid double brackets.
- Tightened the LLM prompts to prefer one-sentence answers where possible.
- Updated the README with the new CLI behavior.
- Added `docs/CONTEXT.md` as a live handoff file for project state.
- Synced the docs with the current CLI behavior, runtime config split, and logging support.
- Changed self-test output to use `[PASS]`/`[FAIL]` prefixes instead of `[SELF-TEST] ... PASS/FAIL`.
- Removed the extra blank line left behind by friendly-mode wait cleanup after successful LLM calls.
- Reviewed the current project structure and decided against a broad refactor for now.
- Identified the LLM transport/provider layer as the smallest worthwhile future extraction.
- Chose the next short-term direction: add local Ollama support with a small provider refactor and local-first fallback to OpenAI on a separate branch.
- Extracted the current OpenAI transport and response parsing into `llm_client.py` as the first small provider-layer refactor.
- Added a provider-facing `generate_text(...)` boundary and threaded `provider` through CLI/runtime while keeping behavior OpenAI-backed for now.
- Added Ollama transport to `llm_client.py`.
- Implemented explicit provider behavior: `openai`, `ollama`, and `auto` with local-first fallback on transport, timeout, availability, or empty-output failure only.
- Added provider-result metadata and verbose logging so fallback behavior is visible during debugging.
- Expanded smoke coverage for OpenAI-only, Ollama-when-available, and `auto` provider behavior.
- Reduced OpenAI token usage with shorter prompts, low reasoning effort, compact JSON routing instructions, and lower output token caps.
- Expanded `--self-test` so it also reports provider-specific generation checks for `openai`, `ollama`, and `auto`.
- Removed overly aggressive OpenAI output caps from the main generation path and relaxed self-test limits after observing truncated incomplete responses.
- Reduced redundant OpenAI self-test calls and treated `auto` rate-limit fallback as `SKIP` instead of `FAIL`.
- Reworked non-deterministic routing so one LLM JSON response now drives both direct answers and tool selection.
- Added a narrow router JSON extractor so recoverable malformed model output can still be used.
- Made `provider=auto` the default CLI provider.
- Added `--timeout` for per-run timeout control.
- Split `auto` timeout budget between the local Ollama attempt and OpenAI fallback.
- Refined verbose terminal output to show input, provider attempts, provider success, and the final answer while keeping raw payloads in the log file.
- Shortened the router prompt substantially after testing showed the longer version slowed local Ollama responses.
- Switched the current local Ollama model target to `qwen3:1.7b` as a better balance than the earlier tested models.
