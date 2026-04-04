import argparse
import msvcrt
import threading
import time

import agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["normal", "verbose", "debug"],
        default=agent.MODE,
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run a small OpenAI API connectivity test and exit.",
    )
    args = parser.parse_args()

    agent.MODE = args.mode

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


if __name__ == "__main__":
    main()
