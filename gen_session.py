import os

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 29214095
api_hash = "927bb297ca5a044cd3e72c661868c6da"

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print(client.session.save())
