from telethon import TelegramClient

api_id = 24746725  # your real API ID
api_hash = '5bdfd0163100b3f7af950e10974764ef'  # your real API hash
phone = '+34645536431'  # your phone number with country code

client = TelegramClient('my_session', api_id, api_hash)

async def main():
    await client.start(phone)
    print("Session created successfully!")

with client:
    client.loop.run_until_complete(main())
