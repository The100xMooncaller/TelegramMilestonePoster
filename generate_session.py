from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 24746725  # your real API ID
api_hash = '5bdfd0163100b3f7af950e10974764ef'  # your real API hash
phone = '+34645536431'  # your phone number with country code

with TelegramClient(StringSession(), api_id, api_hash) as client:
    client.start(phone)
    session_string = client.session.save()
    print("\n✅ SESSION_STRING (copy this for Render):\n")
    print(session_string)
