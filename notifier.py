import httpx


def format_filters_summary(filters: dict) -> str:
    lines = ["✅ Matches your filters:"]

    districts = filters.get("districts", [])
    if districts:
        lines.append(f"• Districts: {', '.join(districts)}")

    min_area = filters.get("min_area")
    if min_area is not None:
        lines.append(f"• Area: min {min_area} m²")

    min_price = filters.get("min_price")
    max_price = filters.get("max_price")
    currency = filters.get("currency", "PLN")
    if min_price is not None and max_price is not None:
        lines.append(f"• Price: {min_price}–{max_price} {currency}")
    elif min_price is not None:
        lines.append(f"• Price: min {min_price} {currency}")
    elif max_price is not None:
        lines.append(f"• Price: max {max_price} {currency}")

    return "\n".join(lines)


def format_listing_summary(details: dict) -> str:
    lines = []

    district = details.get("district")
    if district:
        lines.append(f"📍 District: {district}")

    area = details.get("area")
    if area is not None:
        area_label = int(area) if area == int(area) else area
        lines.append(f"📐 Area: {area_label} m²")

    price = details.get("price")
    if price is not None:
        lines.append(f"💰 Price: {price} PLN")

    return "\n".join(lines)


async def send_match(
    bot_token: str,
    output_channel: str,
    text: str,
    channel_name: str,
    message_link: str,
    posted_at: str,
    lookback_minutes: int,
    filters: dict,
    details: dict,
) -> None:
    preview = text.strip()
    if len(preview) > 600:
        preview = preview[:600] + "..."

    listing_summary = format_listing_summary(details)
    filters_summary = format_filters_summary(filters)

    body = (
        "🏠 RENTAL MATCH — Warsaw\n"
        "🤖 Sent by your rental-filter bot\n\n"
        f"{listing_summary}\n\n"
        f"{filters_summary}\n\n"
        f"📢 Source channel: {channel_name}\n"
        f"🕐 Posted: {posted_at}\n"
        f"⏱ Checked: last {lookback_minutes} minutes\n\n"
        "——— Original listing ———\n"
        f"{preview}\n\n"
        f"🔗 Open listing: {message_link}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url,
            json={
                "chat_id": output_channel,
                "text": body,
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()
