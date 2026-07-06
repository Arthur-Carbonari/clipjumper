def _sentence_case(text):
    result = []
    capitalize_next = True
    for ch in text:
        if capitalize_next and ch.isalpha():
            result.append(ch.upper())
            capitalize_next = False
        else:
            result.append(ch.lower() if ch.isalpha() else ch)
        if ch in ".!?\n":
            capitalize_next = True
    return "".join(result)


def _numbered_list(text):
    lines = text.strip("\r\n").split("\n")
    return "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))


FORMATS = [
    ("None", lambda t: t),
    ("UPPERCASE", str.upper),
    ("lowercase", str.lower),
    ("Sentence case", _sentence_case),
    ("Trim Whitespace", str.strip),
    ("Numbered List", _numbered_list),
]
