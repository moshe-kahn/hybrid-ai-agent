import re
from word2number import w2n

NUMBER_WORDS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety",
    "hundred", "thousand", "million", "billion", "trillion"
}

OPERATION_REPLACEMENTS = {
    "divided by": "/",
    "times": "*",
    "plus": "+",
    "minus": "-",
    "over": "/",
}


def should_force_calculator(user_input):
    text = user_input.lower().strip()

    keywords = ["calculate", "solve", "equation"]
    if any(word in text for word in keywords):
        return True
    
    # Catch natural-language math requests even when they do not contain operator symbols yet.
    if re.search(r"\b(half|quarter)\s+of\b", text):
        return True

    if "**" in text:
        return True

    if re.search(r"\d+\.\d+", text):
        return True

    if "(" in text or ")" in text:
        return True
    
    if re.search(r"\b(sum of|difference between|product of)\b", text):
        return True

    numbers = re.findall(r"\d+", text)
    if any(len(num) >= 4 for num in numbers):
        return True

    if re.search(r"[\+\-\*/]", text):
        return True

    number_words_present = any(
        re.search(rf"\b{word}\b", text) for word in NUMBER_WORDS
    )
    math_words_present = any(
        phrase in text for phrase in OPERATION_REPLACEMENTS
    )
    math_symbols_present = bool(re.search(r"[\+\-\*/]", text))

    if number_words_present and (math_words_present or math_symbols_present):
        return True

    return False


def convert_number_phrases(text):
    tokens = text.split()
    result = []
    i = 0

    while i < len(tokens):
        j = i
        phrase_tokens = []

        while j < len(tokens) and tokens[j] in NUMBER_WORDS:
            phrase_tokens.append(tokens[j])
            j += 1

        if phrase_tokens:
            phrase = " ".join(phrase_tokens)
            try:
                # Convert the longest contiguous run of number words in one pass.
                result.append(str(w2n.word_to_num(phrase)))
                i = j
                continue
            except ValueError:
                pass

        result.append(tokens[i])
        i += 1

    return " ".join(result)


def extract_math_expression(user_input):
    text = user_input.lower().strip()
    # only replace hyphens inside words (e.g., twenty-two → twenty two)
    text = re.sub(r"(?<=[a-zA-Z])-(?=[a-zA-Z])", " ", text)
    text = re.sub(r"(?<=[a-zA-Z0-9])-(?=[0-9])|(?<=[0-9])-(?=[a-zA-Z])|(?<=[0-9])-(?=[0-9])", " - ", text)

    prefixes = ["what is", "calculate", "solve"]
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    text = text.strip(" ?.!")
    text = re.sub(r"^(the|a|an)\s+", "", text)
   

    for phrase, symbol in OPERATION_REPLACEMENTS.items():
        text = text.replace(phrase, f" {symbol} ")

    text = " ".join(text.split())

    text = convert_number_phrases(text)
    text = normalize_negative_phrases(text)
    text = normalize_decimal_phrases(text)

    # Rewrite supported English math phrases into calculator-friendly expressions.
    text = re.sub(r"\bhalf of (\d+(?:\.\d+)?)\b", r"\1 / 2", text)

    text = re.sub(r"\bquarter of (\d+(?:\.\d+)?)\b", r"\1 / 4", text)
    text = re.sub(r"\bsum of (\d+(?:\.\d+)?) and (\d+(?:\.\d+)?)\b", r"\1 + \2", text)
    text = re.sub(r"\bdifference between (\d+(?:\.\d+)?) and (\d+(?:\.\d+)?)\b", r"\1 - \2", text)
    text = re.sub(r"\bproduct of (\d+(?:\.\d+)?) and (\d+(?:\.\d+)?)\b", r"\1 * \2", text)

    return text

def normalize_negative_phrases(text):
    return re.sub(r"\bnegative\s+(\d+)\b", r"-\1", text)

def normalize_decimal_phrases(text):
    return re.sub(r"\b(\d+)\s+point\s+(\d+)\b", r"\1.\2", text)
