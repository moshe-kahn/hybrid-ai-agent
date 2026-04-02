from agent import run_agent

while True:
    user_input = input(">> ")

    if user_input.lower() in ["exit", "quit", "q"]:
        break

    response = run_agent(user_input)
    print(response)