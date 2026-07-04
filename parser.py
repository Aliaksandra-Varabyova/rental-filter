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

PRICE_PATTERNS = [
    re.compile(rf"(\d[\d\s.,]*)\s*{CURRENCY}", re.IGNORECASE),
    re.compile(rf"(\d[\d\s.,]+){CURRENCY}", re.IGNORECASE),
    re.compile(rf"{CURRENCY}\s*(\d[\d\s.,]*)", re.IGNORECASE),
    re.compile(
        r"(?:czynsz|rent|price|koszt|wynajem|цена|стоимость)[:\s]*(\d[\d\s.,]*)",
        re.IGNORECASE,
    ),
    re.compile(r"(\d+(?:[.,]\d+)?)\s*k\b", re.IGNORECASE),
]


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


def parse_prices(text: str) -> list[int]:
    prices: list[int] = []
    for pattern in PRICE_PATTERNS[:-1]:
        for match in pattern.finditer(text):
            prices.append(_parse_number(match.group(1)))
    for match in PRICE_PATTERNS[-1].finditer(text):
        prices.append(int(float(match.group(1).replace(",", ".")) * 1000))
    return prices


def parse_price(text: str, min_price: int | None = None, max_price: int | None = None) -> int | None:
    prices = parse_prices(text)
    if not prices:
        return None
    if min_price is not None and max_price is not None:
        in_range = [price for price in prices if min_price <= price <= max_price]
        if in_range:
            return in_range[0]
    return prices[0]


def parse_area(text: str) -> float | None:
    for pattern in AREA_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


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
}

CANONICAL_DISTRICTS = {
    "zoliborz": "Żoliborz",
    "wola": "Wola",
    "centrum": "Centrum",
}


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
    min_price = filters.get("min_price")
    max_price = filters.get("max_price")
    districts = filters.get("districts", [])

    area = parse_area(text)
    price = parse_price(text, min_price, max_price)
    district = parse_matched_district(text, districts) if districts else None

    return {
        "area": area,
        "price": price,
        "district": district,
    }


def text_contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword_in_text(text, keyword) for keyword in keywords)
