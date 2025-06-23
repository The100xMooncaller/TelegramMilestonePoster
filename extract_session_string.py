from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Load your existing session file
session_file = 'my_session.session'  # Change this if your session file has a different name
api_id = 24746725       # Replace with your actual API ID
api_hash = '5bdfd0163100b3f7af950e10974764ef' # Replace with your actual API Hash

# Load the existing session and print the string version
with TelegramClient(session_file, api_id, api_hash) as client:
    print("Here is your session string:\n")
    print(client.session.save())
