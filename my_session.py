# generate_session.py
from telethon.sync import TelegramClient
import os

API_ID = int(os.getenv("API_ID") 
API_HASH = os.getenv("API_HASH") 
PHONE = os.getenv("PHONE_NUMBER") 

# 'my_session' will create a file: my_session.session
client = TelegramClient("my_session", API_ID, API_HASH)
client.start(phone=PHONE)  # You'll receive code via SMS or Telegram and input it here
client.disconnect()

print("Session file 'my_session.session' generated.")
