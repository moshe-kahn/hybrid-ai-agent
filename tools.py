import requests
import ast
import operator

ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def search_tool(query):
    url = "https://api.duckduckgo.com/"
    
    params = {
        "q": query,
        "format": "json",
        "no_redirect": 1,
        "no_html": 1,
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        # Try to extract useful info
        if data.get("AbstractText"):
            return data["AbstractText"]

        if data.get("RelatedTopics"):
            topics = data["RelatedTopics"]
            if topics and isinstance(topics, list):
                first = topics[0]
                if "Text" in first:
                    return first["Text"]

        return f"No good result found for '{query}'."

    except Exception as e:
        return f"Search error: {str(e)}"
    
def calculator_tool(expression):
    try:
        node = ast.parse(expression, mode="eval").body
        result = _evaluate(node)
        return format_result(result)
    except Exception as e:
        return f"Error in calculation: {e}"

def format_result(result):
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)

def _evaluate(node):
    if isinstance(node, ast.Constant):  # numbers
        return node.value

    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        op_type = type(node.op)

        if op_type in ALLOWED_OPERATORS:
            return ALLOWED_OPERATORS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        operand = _evaluate(node.operand)
        op_type = type(node.op)

        if op_type in ALLOWED_OPERATORS:
            return ALLOWED_OPERATORS[op_type](operand)

    raise ValueError("Unsupported expression")