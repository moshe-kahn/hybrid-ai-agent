# Context

This file is the running handoff note for major project updates. Update it whenever a meaningful change lands so the next session has the current context without reconstructing it from chat history.

## Update Convention

- After behavior change: update `CONTEXT.md`
- Before commit:
  - update `SESSION_NOTES.md`
  - update `KNOWN_ISSUES.md` if the test surface changed
- After debugging session:
  - ensure `KNOWN_ISSUES.md` reflects anything fragile or needing re-test

## How To Use This File

When making a major update, refresh these sections:

1. What changed
2. Recent user requests
3. Current short-term goal
4. Known issues and things to verify
5. Suggested next steps

Keep entries brief and practical. Prefer current state over a long historical log.

## Current Snapshot

- Project: hybrid CLI AI agent that routes between calculator logic, search, and LLM reasoning.
- Main entry point: `main.py`
- Core orchestration: `agent.py`
- Math parsing and detection: `math_utils.py`
- Tools: `tools.py`

## What Changed Recently

- Added CLI mode selection and then split runtime behavior into separate `mode`, `output`, and `connection` settings with mode-implied defaults and explicit overrides.
- Added interactive controls while a request is running:
  - `s` stops waiting and returns to the prompt
  - `q` quits immediately
- Added `--self-test` to verify API key presence, connectivity, model access, and response generation.
- Replaced the hanging OpenAI SDK `responses.create(...)` flow with direct `httpx` calls to `POST /v1/responses`.
- Added app-level timeout handling around LLM requests.
- Improved waiting output:
  - friendly output shows a compact inline `waiting...`
  - verbose output shows per-second labeled wait logs
- Added `scripts/smoke_test.py` for a minimal end-to-end smoke check of calculator behavior, math fallback, and basic LLM response.
- Fixed wait-thread shutdown so progress output is stopped and joined cleanly before process exit.
- Centralized debug printing through a small helper and added timing output for timed request paths in debug mode.
- Expanded smoke coverage with one additional stable natural-language calculator case.
- Added concise completion summaries after timed LLM calls, including elapsed time in all modes and token usage when the API provides it.
- Added an optional `--verbose` mode to `scripts/smoke_test.py` while keeping default smoke output compact.
- Added lightweight shared logging to `logs/latest.log` for each run, with optional extra append logging via `--log-file`.
- Normal-mode `waiting...` now finalizes into a concise completion or failure line instead of leaving partial wait artifacts behind.
- Friendly output now keeps completion summaries minimal, while model and token details remain in verbose/debug output.
- Friendly output now clears successful wait lines without printing a completion summary before the answer.
- Verbose/debug calculator failure logs were shortened to avoid repeating the exact same error line twice.
- Verbose/debug LLM status lines now use a simplified `LLM:<model>` label and avoid redundant post-completion messages.
- Verbose/debug LLM status labels now use bracketed formatting, and corrected-input logging is skipped when the text did not change.
- Verbose/debug wait lines now format as `[LLM:...] WAIT Ns` without double brackets.
- Tightened the LLM prompts to prefer one short sentence whenever possible.
- Updated `README.md` to document the new CLI behavior.
- Synced the docs with the current CLI structure and logging behavior.
- Self-test output now uses `[PASS]`/`[FAIL]` prefixes for readability and consistency with the smoke test.
- Friendly-mode wait cleanup now clears the inline wait indicator without leaving an extra blank line after successful LLM calls.
- Extracted OpenAI transport and response parsing into `llm_client.py` while keeping `agent.py` focused on orchestration.
- Added a public `generate_text(...)` boundary in `llm_client.py` and threaded a separate `provider` setting through the CLI/runtime without changing current OpenAI-backed behavior.
- Added Ollama transport inside `llm_client.py` with explicit `openai`, `ollama`, and `auto` provider behavior.
- Implemented `auto` as local-first with OpenAI fallback only on transport, timeout, provider-unavailable, or empty-output failure.
- Added normalized provider results that include `text`, `provider`, `model`, and `fallback_used`, plus fallback metadata for debugging.
- Added verbose provider-result logging so it is visible which provider was attempted first, why fallback happened, and which provider answered.
- Expanded smoke coverage for OpenAI-only, Ollama-when-available, and `auto` provider behavior.
- Tightened OpenAI prompt construction to reduce token usage with shorter stable system prompts, lower output caps, low reasoning effort, and compact JSON routing output.
- Expanded `--self-test` with provider-aware generation checks for `openai`, `ollama`, and `auto`.
- Relaxed aggressive output caps after GPT-5-nano self-tests showed that tiny visible answers can still require much larger total output-token budgets.
- Reduced redundant OpenAI self-test calls and allowed `auto` self-test to report `SKIP` on fallback rate limits instead of a misleading hard failure.
- Reworked non-deterministic routing so one LLM JSON response now drives both direct answers and tool selection.
- Added a narrow router JSON extractor so recoverable malformed model output can still be used.
- Made `provider=auto` the default CLI provider and added `--timeout` for per-run timeout control.
- Split `auto` timeout budget between the local Ollama attempt and OpenAI fallback.
- Refined verbose terminal output so it now emphasizes input, provider attempts, provider success, and the final answer while keeping raw payloads in `logs/latest.log`.
- Shortened the router prompt after testing showed the longer policy-heavy version slowed local Ollama responses.
- Updated the current local Ollama model target to `qwen3:1.7b`.

## Recent User Requests

- Add minimal comments only where intent is non-obvious.
- Add command-line mode selection with `argparse`.
- Make LLM wait/debug behavior visible.
- Add timeouts and request interruption controls.
- Diagnose why LLM fallback was hanging.
- Add a stronger self-test that checks multiple layers.
- Update the README with the new workflow.
- Add this context file for future major updates.
- Reconstruct the latest checkpoint from repo docs and git state.
- Assess whether the current file structure should stay as-is or take a small refactor.
- Plan a small LLM-provider refactor so a local Ollama model can be tried first and OpenAI can remain the fallback.
- Use a branch for that provider refactor rather than changing the current checkpoint in place.
- Separate the LLM request layer from `agent.py` as the first small step toward multi-provider support.
- Add Ollama transport and explicit local-first fallback behavior while keeping `connection` and `provider` separate.
- Make `provider=auto` the default.
- Make timeout configurable from the CLI.
- Keep verbose terminal output readable while logs keep the raw details.
- Avoid a naive deterministic factual detector for now.
- Leave dedicated math fallback as a future action item.

## Current Short-Term Goal

- Keep the CLI stable and easy to debug.
- Preserve the working direct-HTTP OpenAI path.
- Keep the runtime config model easy to reason about and re-test.
- Keep friendly output compact and clean.
- Make future sessions easier by keeping docs aligned with the code.
- Keep the new `llm_client.py` boundary stable and easy to reason about.
- Keep the current local-first `auto` flow usable and easy to inspect.
- Avoid a broad redesign; keep further fixes narrow and centered on routing policy and provider behavior.

## Known Issues And Things To Verify

- Re-check `README.md` in the editor after the rewrite to confirm the encoding cleanup is fully resolved.
- The stop action is a soft cancel of the local wait. It does not guarantee the in-flight HTTP request is truly aborted server-side.
- The waiting indicator and threaded timeout flow should be re-tested after any future refactor touching CLI control flow.
- `--self-test` currently checks many layers and prints results directly; if the output format changes later, keep it readable in both friendly and verbose usage.
- Runtime behavior now depends on the interaction between `mode`, `output`, and `connection`; CLI resolution changes should be re-tested carefully.
- `agent.py` is still the highest-pressure file, but provider transport is now separated into `llm_client.py`.
- Ollama availability and local-first fallback behavior should be re-tested outside the sandbox because local model availability is environment-specific.
- The current local model (`qwen3:1.7b`) is much more usable than earlier local attempts, but it can still answer factual/current questions directly instead of routing to search.
- Calculator parse failure still uses a direct LLM fallback; the intended dedicated math fallback remains a future item.
- `auto` timeout splitting is now in place, but very small budgets can still fail simply because neither provider gets enough useful time to answer.

## What We Believe Is True Right Now

- API key, network reachability, authenticated model access, and direct `/v1/responses` calls are working.
- The earlier hanging issue was isolated to the SDK-based response call path in this environment.
- The current direct `httpx` implementation is the preferred request path for this repo.
- The latest uncommitted checkpoint adds the runtime config split, shared logging, and doc updates around that work.
- The smallest justified refactor was to separate provider transport from orchestration so multiple LLM backends can be supported cleanly.
- The provider layer now supports OpenAI, Ollama, and explicit `auto` fallback rules while keeping `connection` separate from `provider`.
- The current non-deterministic path uses one structured router call per request.
- The current default provider is `auto`, with local Ollama attempted first and OpenAI fallback when allowed.

## Suggested Next Steps

- Commit the current provider/fallback/routing checkpoint if the docs look right.
- Re-run a couple of manual checks for `--provider ollama` and default `auto` after any further prompt tweaks.
- Decide whether to enforce factual/current lookup in code rather than relying on prompt-only routing.
- Keep future work narrow around routing policy, dedicated math fallback, and tool quality.
