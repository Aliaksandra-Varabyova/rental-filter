import re
import unicodedata

METER = r"[mм]"
SQUARE = r"(?:²|2)"
CURRENCY = r"(?:zł|zl|zlotych|złotych|pln)"

AREA_PATTERNS = [
    re.compile(rf"(\d+(?:[.,]\d+)?)\s*{METER}\s*{SQUARE}", re.IGNORECASE),
    re.compile(rf"(\d+(?:[.,]\d+)?){METER}{SQUARE}", re.IGNORECASE),
    re.compile(r"(\d+(?:[.,]\d+)?)\s*sqm", re.IGNORECASE),
    re.compile(r"(\d+(?:[.,]\d+)?)\s*кв\.?\s*м", re.IGNORECASE),
]

PRICE_WITH_CURRENCY = re.compile(
    rf"(\d[\d\s.,]+)\s*{CURRENCY}",
    re.IGNORECASE,
)

PLUS_CZYNSZ_PATTERN = re.compile(
    rf"(\d[\d\s.,]*)\s*(?:{CURRENCY})?\s*\+\s*(\d[\d\s.,]*)\s*(?:{CURRENCY})?\s*czynsz",
    re.IGNORECASE,
)

CZYNSZ_PATTERN = re.compile(
    rf"(\d[\d\s.,]*)\s*(?:{CURRENCY})?\s*czynsz",
    re.IGNORECASE,
)

RENT_LABEL_PATTERN = re.compile(
    r"(?:wynajem|rent|аренда|arenda|najmu)[:\s]*(\d[\d\s.,]*)",
    re.IGNORECASE,
)

K_PRICE_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*k\b", re.IGNORECASE)

NON_RENT_KEYWORDS = (
    "czynsz",
    "czynsj",
    "administracja",
    "adm ",
    " media",
    "deposit",
    "kaucja",
    "depozyt",
    "zadatek",
    "депозит",
    "depozit",
    "parking",
    "garage",
    "garaz",
    "garaż",
    "парковка",
    "kladowa",
    "klatev",
    "кладовая",
    "komorka",
    "komórka",
    "piwnica",
    "pogreb",
    "погреб",
    "🔐",
)

RENT_KEYWORDS = (
    "wynajem",
    "rent",
    "аренда",
    "arenda",
    "najmu",
    "mieszkania",
)

DISTRICT_ALIASES: dict[str, list[str]] = {
    "zoliborz": [
        "Żoliborz",
        "Zoliborz",
        "ZOLIBORZ",
        "zoliborz",
        "Жолибож",
        "жолибож",
        "Zholiborzh",
        "zholiborzh",
    ],
    "wola": [
        "Wola",
        "WOLA",
        "wola",
        "Vola",
        "vola",
        "Вола",
        "вола",
    ],
    "centrum": [
        "Centrum",
        "CENTRUM",
        "centrum",
        "Śródmieście",
        "Srodmiescie",
        "ŚRÓDMIEŚCIE",
        "srodmiescie",
        "Center",
        "Centre",
        "CENTER",
        "centre",
        "center",
        "Downtown",
        "downtown",
        "Центр",
        "центр",
        "Tsentr",
        "tsentr",
    ],
    "mokotow": [
        "Mokotów",
        "Mokotow",
        "MOKOTOW",
        "mokotow",
        "Mokotowo",
        "Мокотów",
        "Мокotów",
        "Мокотово",
        "мокotów",
        "мокотово",
        "Mokotov",
        "mokotov",
    ],
}

CANONICAL_DISTRICTS = {
    "zoliborz": "Żoliborz",
    "wola": "Wola",
    "centrum": "Centrum",
    "mokotow": "Mokotów",
}


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text)
    without_marks = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    return without_marks.casefold()


def keyword_in_text(text: str, keyword: str) -> bool:
    if keyword.lower() in text.lower():
        return True

    normalized_keyword = normalize(keyword)
    if not normalized_keyword:
        return False

    normalized_text = normalize(text)
    if normalized_keyword in normalized_text:
        return True

    pattern = rf"(?<![\w]){re.escape(normalized_keyword)}(?![\w])"
    return re.search(pattern, normalized_text, re.UNICODE) is not None


def _parse_number(value: str) -> int:
    cleaned = value.replace(" ", "").replace(",", "")
    return int(float(cleaned))


def _context_window(text: str, start: int, end: int, radius: int = 40) -> str:
    return text[max(0, start - radius): min(len(text), end + radius)].casefold()


def _is_non_rent_context(context: str) -> bool:
    return any(keyword in context for keyword in NON_RENT_KEYWORDS)


def _is_rent_context(context: str) -> bool:
    return any(keyword in context for keyword in RENT_KEYWORDS)


def parse_czynsz(text: str) -> int | None:
    plus_match = PLUS_CZYNSZ_PATTERN.search(text)
    if plus_match:
        return _parse_number(plus_match.group(2))

    czynsz_match = CZYNSZ_PATTERN.search(text)
    if czynsz_match:
        return _parse_number(czynsz_match.group(1))

    return None


def parse_rent_price(text: str) -> int | None:
    plus_match = PLUS_CZYNSZ_PATTERN.search(text)
    if plus_match:
        return _parse_number(plus_match.group(1))

    rent_label_match = RENT_LABEL_PATTERN.search(text)
    if rent_label_match:
        return _parse_number(rent_label_match.group(1))

    candidates: list[tuple[int, int]] = []

    for match in PRICE_WITH_CURRENCY.finditer(text):
        context = _context_window(text, match.start(), match.end())
        if _is_non_rent_context(context):
            continue

        value = _parse_number(match.group(1))
        priority = 2 if _is_rent_context(context) else 1
        candidates.append((value, priority))

    for match in K_PRICE_PATTERN.finditer(text):
        context = _context_window(text, match.start(), match.end())
        if _is_non_rent_context(context):
            continue

        value = int(float(match.group(1).replace(",", ".")) * 1000)
        priority = 2 if _is_rent_context(context) else 1
        candidates.append((value, priority))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[1], -item[0]))
    return candidates[0][0]


def parse_price(
    text: str,
    min_price: int | None = None,
    max_price: int | None = None,
) -> int | None:
    return parse_rent_price(text)


def parse_area(text: str) -> float | None:
    for pattern in AREA_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def district_group(keyword: str) -> str | None:
    normalized_keyword = normalize(keyword)
    for group, aliases in DISTRICT_ALIASES.items():
        if normalized_keyword == group:
            return group
        for alias in aliases:
            if normalized_keyword == normalize(alias):
                return group
    return None


def expand_districts(districts: list[str]) -> list[str]:
    expanded: set[str] = set()
    for district in districts:
        expanded.add(district)
        group = district_group(district)
        if group:
            expanded.update(DISTRICT_ALIASES[group])
    return list(expanded)


def parse_matched_district(text: str, districts: list[str]) -> str | None:
    for variant in expand_districts(districts):
        if not text_contains_any(text, [variant]):
            continue
        group = district_group(variant)
        if group:
            return CANONICAL_DISTRICTS.get(group, variant)
        return variant
    return None


def district_match(text: str, districts: list[str]) -> bool:
    return parse_matched_district(text, districts) is not None


def extract_listing_details(text: str, filters: dict) -> dict:
    districts = filters.get("districts", [])

    return {
        "area": parse_area(text),
        "price": parse_rent_price(text),
        "czynsz": parse_czynsz(text),
        "district": parse_matched_district(text, districts) if districts else None,
    }


def text_contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword_in_text(text, keyword) for keyword in keywords)
