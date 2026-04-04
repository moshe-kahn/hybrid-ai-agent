import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from tools import search_tool, calculator_tool
from math_utils import should_force_calculator, extract_math_expression

from spellchecker import SpellChecker

# Valid modes: "normal", "verbose", "debug"
MODE = "normal"

def is_verbose():
    return MODE in ("verbose", "debug")

def is_debug():
    return MODE == "debug"

load_dotenv()

spell = SpellChecker()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

TOOLS = {
    "search_tool": search_tool,
}

SYSTEM_PROMPT = """
You are a tool-using assistant.

Rules:
- Use search_tool when:
- the question is about current events, recent data, or real-time information
- you are unsure of the answer
- the query clearly requires external lookup

- For simple definitions or well-known concepts, you may answer directly with tool = "none"

IMPORTANT:
- When tool = "none", the "input" field MUST contain your actual response to the user
- Never return "input": "none"

Available tools:
1. search_tool(query)

Valid formats:
{"tool": "search_tool", "input": "fastapi"}
{"tool": "none", "input": "Hello! How can I help you?"}

Return exactly one JSON object and nothing else.
Do not include markdown.
Do not include any text before or after the JSON.

Be concise by default. Expand only if the problem requires explanation.
"""
def safe_correct_text(text):
    words = text.split()
    corrected = []

    for word in words:
        # skip numbers
        if any(char.isdigit() for char in word):
            corrected.append(word)
            continue

        # skip math symbols
        if any(op in word for op in "+-*/"):
            corrected.append(word)
            continue

        fixed = spell.correction(word)
        corrected.append(fixed if fixed else word)

    return " ".join(corrected)

def run_agent(user_input):
    corrected_input = safe_correct_text(user_input)
    if is_verbose():
        print(f"[CORRECTED INPUT] {corrected_input}")
    user_input = corrected_input

    if should_force_calculator(user_input):
        expr = extract_math_expression(user_input)
        calc_result = calculator_tool(expr)

        if not str(calc_result).startswith("Error in calculation"):
            if is_verbose():
                print(f"[CALCULATOR] {user_input} -> {expr} -> {calc_result}")
            return calc_result
        else:
            if is_verbose():
                print(f"[CALCULATOR FAILED] {user_input} -> {expr} -> {calc_result}")

            if is_debug():
                return calc_result

            try:
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
            except Exception as e:
                return f"OpenAI API error during math fallback: {e}"

    if is_verbose():
        print(f"[LLM] {user_input}")

    if is_debug():
        return "DEBUG MODE: LLM call skipped"

    try:
        response = client.responses.create(
            model="gpt-5-nano",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
        )

        reply_text = response.output_text.strip()
        if is_verbose():
            print(f"[ROUTER RAW] {reply_text}")
    except Exception as e:
        return f"OpenAI API error during tool routing: {e}"

    try:
        decision = json.loads(reply_text)
    except json.JSONDecodeError:
        return f"Model returned invalid JSON: {reply_text}"

    tool_name = decision.get("tool")
    tool_input = decision.get("input", "")

    if tool_name in TOOLS:
        if is_verbose():
            print(f"[SEARCH] {tool_input}")
        tool_result = TOOLS[tool_name](tool_input)

        response = client.responses.create(
            model="gpt-5-nano",
            input=[
                {
                    "role": "system",
                    "content": "Use the tool result as your primary source. If it is incomplete or unhelpful, you may supplement with general knowledge, but clearly indicate uncertainty."
                },
                {
                    "role": "user",
                    "content": f"User asked: {user_input}\nTool returned: {tool_result}"
                },
            ],
        )

        return response.output_text.strip()

    if tool_name == "none":
        if tool_input.strip().lower() == "none":
            return "I'm not sure how to respond to that."
        return tool_input