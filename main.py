import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import Channel, DialogFilter

from filter import matches_filters
from notifier import send_match

SEEN_IDS_PATH = Path("seen_ids.json")
CONFIG_PATH = Path("config.yaml")


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_seen_ids() -> set[str]:
    if not SEEN_IDS_PATH.exists():
        return set()
    data = json.loads(SEEN_IDS_PATH.read_text(encoding="utf-8"))
    return set(data.get("ids", []))


def save_seen_ids(seen_ids: set[str]) -> None:
    trimmed = sorted(seen_ids)[-5000:]
    SEEN_IDS_PATH.write_text(
        json.dumps({"ids": trimmed}, indent=2),
        encoding="utf-8",
    )


def message_link(entity: Channel, message_id: int) -> str:
    username = getattr(entity, "username", None)
    if username:
        return f"https://t.me/{username}/{message_id}"

    channel_id = str(abs(entity.id))
    if channel_id.startswith("100"):
        channel_id = channel_id[3:]
    return f"https://t.me/c/{channel_id}/{message_id}"


def channel_label(entity: Channel) -> str:
    username = getattr(entity, "username", None)
    title = getattr(entity, "title", None)
    if username:
        return f"@{username}"
    if title:
        return title
    return str(entity.id)


async def get_folder_channels(client: TelegramClient, folder_name: str) -> list[Channel]:
    response = await client(GetDialogFiltersRequest())
    for dialog_filter in response.filters:
        if not isinstance(dialog_filter, DialogFilter):
            continue
        if dialog_filter.title != folder_name:
            continue

        channels: list[Channel] = []
        for peer in dialog_filter.include_peers:
            entity = await client.get_entity(peer)
            if isinstance(entity, Channel):
                channels.append(entity)
        return channels

    raise ValueError(f'Folder "{folder_name}" not found on this Telegram account')


async def run() -> None:
    api_id = int(os.environ["TG_API_ID"])
    api_hash = os.environ["TG_API_HASH"]
    bot_token = os.environ["TG_BOT_TOKEN"]
    session_string = os.environ["TG_SESSION"]
    output_channel = os.environ["TG_OUTPUT_CHANNEL"]

    config = load_config()
    folder_name = config["folder"]
    filters = config["filters"]
    lookback_minutes = config.get("lookback_minutes", 65)

    seen_ids = load_seen_ids()
    newly_seen: set[str] = set()
    matches_sent = 0
    messages_checked = 0

    since = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)

    async with TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
    ) as client:
        channels = await get_folder_channels(client, folder_name)
        print(f'Found {len(channels)} channels in folder "{folder_name}"')

        for channel in channels:
            label = channel_label(channel)
            async for message in client.iter_messages(channel, limit=200):
                if not message.text:
                    continue

                message_date = message.date
                if message_date.tzinfo is None:
                    message_date = message_date.replace(tzinfo=timezone.utc)
                if message_date < since:
                    break

                messages_checked += 1
                dedupe_key = f"{channel.id}:{message.id}"
                if dedupe_key in seen_ids or dedupe_key in newly_seen:
                    continue

                newly_seen.add(dedupe_key)
                is_match, reason = matches_filters(message.text, filters)
                if not is_match:
                    print(f"Skip {label}/{message.id}: {reason}")
                    continue

                await send_match(
                    bot_token=bot_token,
                    output_channel=output_channel,
                    text=message.text,
                    channel_name=label,
                    message_link=message_link(channel, message.id),
                )
                matches_sent += 1
                print(f"Sent match from {label}/{message.id}")

    seen_ids.update(newly_seen)
    save_seen_ids(seen_ids)
    print(
        f"Done. Checked {messages_checked} messages, sent {matches_sent} matches."
    )


if __name__ == "__main__":
    asyncio.run(run())
