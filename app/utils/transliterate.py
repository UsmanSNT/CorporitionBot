"""
Uzbek/Russian text normalization for keyword matching.
Converts any script (Cyrillic/Latin) to a common comparable form.
"""

CYR_TO_LAT = {
    ‘а’: ‘a’, ‘б’: ‘b’, ‘в’: ‘v’, ‘г’: ‘g’, ‘д’: ‘d’,
    ‘е’: ‘e’, ‘ё’: ‘yo’, ‘ж’: ‘j’, ‘з’: ‘z’, ‘и’: ‘i’,
    ‘й’: ‘y’, ‘к’: ‘k’, ‘л’: ‘l’, ‘м’: ‘m’, ‘н’: ‘n’,
    ‘о’: ‘o’, ‘п’: ‘p’, ‘р’: ‘r’, ‘с’: ‘s’, ‘т’: ‘t’,
    ‘у’: ‘u’, ‘ф’: ‘f’, ‘х’: ‘x’, ‘ц’: ‘ts’, ‘ч’: ‘ch’,
    ‘ш’: ‘sh’, ‘щ’: ‘sh’, ‘ъ’: ‘’, ‘ы’: ‘i’, ‘ь’: ‘’,
    ‘э’: ‘e’, ‘ю’: ‘yu’, ‘я’: ‘ya’,
    ‘қ’: ‘q’, ‘ғ’: ‘g’, ‘ҳ’: ‘h’, ‘ў’: ‘o’, ‘ң’: ‘ng’,
}


def normalize(text: str) -> str:
    """Convert text to a comparable Latin form, lowercased, no apostrophes."""
    text = text.lower()
    result = []
    for ch in text:
        result.append(CYR_TO_LAT.get(ch, ch))
    joined = ‘’.join(result)
    # Remove apostrophes used in Uzbek Latin (o’, g’)
    joined = joined.replace("’", "").replace("’", "").replace("ʼ", "")
    return joined


def keyword_matches(keyword: str, text: str) -> bool:
    """Return True if keyword appears in text, regardless of script."""
    if not keyword or not text:
        return not keyword
    kw = normalize(keyword)
    tx = normalize(text)
    return kw in tx
