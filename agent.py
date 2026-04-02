import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from tools import search_tool, calculator_tool
from math_utils import should_force_calculator, extract_math_expression

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

TOOLS = {
    "search_tool": search_tool,
}

SYSTEM_PROMPT = """
You are a tool-using assistant.

Rules:
- If the user asks about facts, definitions, or external info -> use search_tool
- Only respond with "none" for casual conversation
- Return exactly one JSON object and nothing else

Available tools:
1. search_tool(query)

Valid formats:
{"tool": "search_tool", "input": "fastapi"}
{"tool": "none", "input": "your normal reply"}

Do not include markdown.
Do not include any text before or after the JSON.
"""


def run_agent(user_input):
    if should_force_calculator(user_input):
        expr = extract_math_expression(user_input)
        calc_result = calculator_tool(expr)

        if calc_result != "Error in calculation":
            print(f"[CALCULATOR] {user_input} -> {expr} -> {calc_result}")
            return calc_result
        else:
            print(f"[CALCULATOR FAILED → LLM] {user_input} -> {expr}")
            response = client.responses.create(
                model="gpt-5-nano",
                input=[
                    {
                        "role": "system",
                        "content": "The user's input may be an unusual or poorly phrased math question. Try to answer it directly if possible. If the intent is unclear, say so briefly."
                    },
                    {
                        "role": "user",
                        "content": user_input
                    },
                ],
            )
            return response.output_text.strip()
    print(f"[LLM] {user_input}")
    response = client.responses.create(
        model="gpt-5-nano",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
    )

    reply_text = response.output_text.strip()

    try:
        decision = json.loads(reply_text)
    except json.JSONDecodeError:
        return f"Model returned invalid JSON: {reply_text}"

    tool_name = decision.get("tool")
    tool_input = decision.get("input", "")

    if tool_name in TOOLS:
        print(f"[SEARCH] {tool_input}")
        tool_result = TOOLS[tool_name](tool_input)

        response = client.responses.create(
            model="gpt-5-nano",
            input=[
                {
                    "role": "system",
                    "content": "Answer the user's question using only the tool result. If the tool result is limited, be honest about that and do not add outside facts."
                },
                {
                    "role": "user",
                    "content": f"User asked: {user_input}\nTool returned: {tool_result}"
                },
            ],
        )

        return response.output_text.strip()

    return tool_input