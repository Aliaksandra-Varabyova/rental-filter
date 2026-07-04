import re
import unicodedata

AREA_PATTERNS = [
    re.compile(r"(\d+(?:[.,]\d+)?)\s*m²", re.IGNORECASE),
    re.compile(r"(\d+(?:[.,]\d+)?)\s*m2\b", re.IGNORECASE),
    re.compile(r"(\d+(?:[.,]\d+)?)\s*sqm", re.IGNORECASE),
]

PRICE_PATTERNS = [
    re.compile(r"(\d[\d\s.,]*)\s*(?:zł|zl|pln|złotych|zlotych)", re.IGNORECASE),
    re.compile(
        r"(?:czynsz|rent|price|koszt|wynajem)[:\s]*(\d[\d\s.,]*)",
        re.IGNORECASE,
    ),
    re.compile(r"(\d+(?:[.,]\d+)?)\s*k\b", re.IGNORECASE),
]


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text)
    ascii_text = folded.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


def _parse_number(value: str) -> int:
    cleaned = value.replace(" ", "").replace(",", "")
    return int(float(cleaned))


def parse_prices(text: str) -> list[int]:
    prices: list[int] = []
    for pattern in PRICE_PATTERNS[:2]:
        for match in pattern.finditer(text):
            prices.append(_parse_number(match.group(1)))
    for match in PRICE_PATTERNS[2].finditer(text):
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


def parse_matched_district(text: str, districts: list[str]) -> str | None:
    for district in districts:
        if text_contains_any(text, [district]):
            return district
    return None


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
    normalized_text = normalize(text)
    lowered_text = text.lower()
    for keyword in keywords:
        if keyword.lower() in lowered_text:
            return True
        if normalize(keyword) in normalized_text:
            return True
    return False
