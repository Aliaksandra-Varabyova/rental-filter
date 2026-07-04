import httpx


async def send_match(
    bot_token: str,
    output_channel: str,
    text: str,
    channel_name: str,
    message_link: str,
) -> None:
    preview = text.strip()
    if len(preview) > 800:
        preview = preview[:800] + "..."

    body = (
        f"🏠 Match from {channel_name}\n\n"
        f"{preview}\n\n"
        f"🔗 {message_link}"
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
