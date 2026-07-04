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
from parser import extract_listing_details

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


def filter_title(dialog_filter: DialogFilter) -> str:
    title = dialog_filter.title
    if hasattr(title, "text"):
        return title.text
    return str(title)


async def get_folder_channels(client: TelegramClient, folder_name: str) -> list[Channel]:
    response = await client(GetDialogFiltersRequest())
    available_folders: list[str] = []

    for dialog_filter in response.filters:
        if not isinstance(dialog_filter, DialogFilter):
            continue

        title = filter_title(dialog_filter)
        available_folders.append(title)
        if title != folder_name:
            continue

        channels: list[Channel] = []
        for peer in dialog_filter.include_peers:
            entity = await client.get_entity(peer)
            if isinstance(entity, Channel):
                channels.append(entity)
        return channels

    folders_list = ", ".join(available_folders) or "none"
    raise ValueError(
        f'Folder "{folder_name}" not found. Available folders: {folders_list}'
    )


async def run() -> None:
    api_id = int(os.environ["TG_API_ID"])
    api_hash = os.environ["TG_API_HASH"]
    bot_token = os.environ["TG_BOT_TOKEN"]
    session_string = os.environ["TG_SESSION"]
    output_channel = os.environ["TG_OUTPUT_CHANNEL"]

    config = load_config()
    folder_name = config["folder"]
    filters = config["filters"]
    lookback_minutes = config.get("lookback_minutes", 60)

    seen_ids = load_seen_ids()
    newly_seen: set[str] = set()
    matches_sent = 0
    messages_in_window = 0
    already_seen_count = 0
    no_text_count = 0
    skip_reasons: dict[str, int] = {}

    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=lookback_minutes)

    print("=== Rental filter run ===")
    print(f"Time window: {since.strftime('%Y-%m-%d %H:%M UTC')} → {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Lookback: {lookback_minutes} minutes")
    print(f"Active filters: {filters}")
    print(f"Previously seen messages stored: {len(seen_ids)}")
    print()

    async with TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
    ) as client:
        channels = await get_folder_channels(client, folder_name)
        print(f'Found {len(channels)} channels in folder "{folder_name}":')
        for channel in channels:
            print(f"  • {channel_label(channel)}")
        print()

        for channel in channels:
            label = channel_label(channel)
            channel_in_window = 0
            channel_already_seen = 0
            channel_matches = 0
            channel_skips: dict[str, int] = {}

            async for message in client.iter_messages(channel, limit=200):
                if not message.text:
                    no_text_count += 1
                    continue

                message_date = message.date
                if message_date.tzinfo is None:
                    message_date = message_date.replace(tzinfo=timezone.utc)
                if message_date < since:
                    break

                messages_in_window += 1
                channel_in_window += 1
                dedupe_key = f"{channel.id}:{message.id}"

                if dedupe_key in seen_ids or dedupe_key in newly_seen:
                    already_seen_count += 1
                    channel_already_seen += 1
                    print(
                        f"Already seen {label}/{message.id} "
                        f"({message_date.strftime('%H:%M UTC')}) — skipped"
                    )
                    continue

                newly_seen.add(dedupe_key)
                is_match, reason = matches_filters(message.text, filters)
                if not is_match:
                    skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                    channel_skips[reason] = channel_skips.get(reason, 0) + 1
                    print(f"Skip {label}/{message.id}: {reason}")
                    continue

                await send_match(
                    bot_token=bot_token,
                    output_channel=output_channel,
                    text=message.text,
                    channel_name=label,
                    message_link=message_link(channel, message.id),
                    posted_at=message_date.strftime("%Y-%m-%d %H:%M UTC"),
                    lookback_minutes=lookback_minutes,
                    filters=filters,
                    details=extract_listing_details(message.text, filters),
                )
                matches_sent += 1
                channel_matches += 1
                print(f"✅ Sent match from {label}/{message.id}")

            skip_summary = ", ".join(f"{reason}={count}" for reason, count in channel_skips.items())
            print(
                f"Channel {label}: {channel_in_window} in window, "
                f"{channel_already_seen} already seen, "
                f"{channel_matches} sent"
                + (f", skipped: {skip_summary}" if skip_summary else "")
            )

    seen_ids.update(newly_seen)
    save_seen_ids(seen_ids)

    print()
    print("=== Summary ===")
    print(f"Messages in last {lookback_minutes} min: {messages_in_window}")
    print(f"Already seen (from previous runs): {already_seen_count}")
    print(f"No text (photos only etc.): {no_text_count}")
    if skip_reasons:
        print("Filtered out:")
        for reason, count in sorted(skip_reasons.items()):
            print(f"  • {reason}: {count}")
    print(f"Matches sent to Telegram: {matches_sent}")
    print(f"New messages stored: {len(newly_seen)}")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyError as error:
        print(f"Missing environment variable: {error}")
        raise SystemExit(1) from error
    except Exception as error:
        print(f"Error: {error}")
        raise SystemExit(1) from error
