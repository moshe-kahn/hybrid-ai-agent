import argparse
import msvcrt
from pathlib import Path
import threading
import time

import agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["normal", "debug"],
        default="normal",
    )
    parser.add_argument(
        "--output",
        choices=["friendly", "verbose"],
    )
    parser.add_argument(
        "--connection",
        choices=["api", "local"],
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "ollama", "auto"],
        default="openai",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run a small OpenAI API connectivity test and exit.",
    )
    parser.add_argument(
        "--log-file",
        help="Optional additional log file to append shared debug/status output to.",
    )
    args = parser.parse_args()

    resolved_output = args.output
    resolved_connection = args.connection

    if args.mode == "normal":
        if resolved_output is None:
            resolved_output = "friendly"
        if resolved_connection is None:
            resolved_connection = "api"
    else:
        if resolved_output is None:
            resolved_output = "verbose"
        if resolved_connection is None:
            resolved_connection = "local"

    log_paths = [Path("logs/latest.log")]
    if args.log_file:
        log_paths.append(Path(args.log_file))

    agent.configure_runtime(
        mode=args.mode,
        output=resolved_output,
        connection=resolved_connection,
        provider=args.provider,
        log_paths=log_paths,
    )

    def run_with_controls(func):
        result = {"response": None}

        def run_query():
            result["response"] = func()

        worker = threading.Thread(target=run_query, daemon=True)
        worker.start()

        while worker.is_alive():
            if msvcrt.kbhit():
                key = msvcrt.getwch().lower()
                if key == "s":
                    agent.request_stop()
                    print("[STOPPED] Query cancelled by user")
                    break
                if key == "q":
                    agent.request_stop()
                    print("\n[QUIT] Exiting program")
                    return False
            time.sleep(0.05)

        if worker.is_alive():
            return True

        if result["response"] is not None:
            print(result["response"])
        return True

    try:
        if args.self_test:
            run_with_controls(agent.run_self_test)
            return

        while True:
            user_input = input(">> ")

            if user_input.lower() in ["exit", "quit", "q"]:
                print("[QUIT] Exiting program")
                break

            should_continue = run_with_controls(lambda: agent.run_agent(user_input))
            if not should_continue:
                return
    finally:
        agent.close_runtime()


if __name__ == "__main__":
    main()
