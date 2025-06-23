from telethon.sync import TelegramClient

# Replace with your actual values
api_id = 24746725
api_hash = '5bdfd0163100b3f7af950e10974764ef'

client = TelegramClient("my_session", api_id, api_hash)

client.start()  # This will prompt for phone number + code
print("✅ Authorized and session file created.")