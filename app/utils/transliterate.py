"""
Uzbek/Russian text normalization for keyword matching.
Converts any script (Cyrillic/Latin) to a common comparable form.
"""

CYR_TO_LAT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
    'е': 'e', 'ё': 'yo', 'ж': 'j', 'з': 'z', 'и': 'i',
    'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
    'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
    'у': 'u', 'ф': 'f', 'х': 'x', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'sh', 'ъ': '', 'ы': 'i', 'ь': '',
    'э': 'e', 'ю': 'yu', 'я': 'ya',
    'қ': 'q', 'ғ': 'g', 'ҳ': 'h', 'ў': 'o', 'ң': 'ng',
}

_APOSTROPHES = ('‘', '’', 'ʼ', "'")


def normalize(text):
    """Convert text to a comparable Latin form, lowercased, no apostrophes."""
    text = text.lower()
    result = []
    for ch in text:
        result.append(CYR_TO_LAT.get(ch, ch))
    joined = ''.join(result)
    for apos in _APOSTROPHES:
        joined = joined.replace(apos, '')
    return joined


def keyword_matches(keyword, text):
    """Return True if keyword appears in text, regardless of script."""
    if not keyword or not text:
        return not keyword
    kw = normalize(keyword)
    tx = normalize(text)
    return kw in tx
