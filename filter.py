from parser import parse_area, parse_price, text_contains_any


def matches_filters(text: str, filters: dict) -> tuple[bool, str]:
    if not text or not text.strip():
        return False, "empty message"

    cities = filters.get("city", [])
    if cities and not text_contains_any(text, cities):
        return False, "city mismatch"

    districts = filters.get("districts", [])
    if districts and not text_contains_any(text, districts):
        return False, "district mismatch"

    min_area = filters.get("min_area")
    if min_area is not None:
        area = parse_area(text)
        if area is None:
            return False, "area not found"
        if area < min_area:
            return False, f"area too small ({area} m²)"

    min_price = filters.get("min_price")
    max_price = filters.get("max_price")
    if min_price is not None or max_price is not None:
        price = parse_price(text, min_price, max_price)
        if price is None:
            return False, "price not found"
        if min_price is not None and price < min_price:
            return False, f"price too low ({price} PLN)"
        if max_price is not None and price > max_price:
            return False, f"price too high ({price} PLN)"

    return True, "match"
