import json


DICTIONARY = json.load(open("files/dictionary.json", "r", encoding="utf-8"))


def extract_params_from_text(text: str) -> list[str]:
    return list(filter(bool, [x.strip() for x in text.split("\n")]))


def get_text(key: str, lang: str) -> str:
    return DICTIONARY[key][lang]
