import os
import re
import logging
import time
import math
import asyncio
import requests
import aiohttp
import random 

from dotenv import load_dotenv
from telethon import TelegramClient, events
from functools import partial
from io import BytesIO
from telegram import Bot
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask
from threading import Thread
import base64

# --- Load environment variables --- #
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
GROUP_ID = int(os.getenv("PRIVATE_GROUP_ID"))
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDENTIALS_PATH = os.getenv("GOOGLE_SHEET_CREDENTIALS")
BOT_TOKEN = os.getenv("BOT_TOKEN")

PUBLIC_CHANNEL = os.getenv("PUBLIC_CHANNEL", "-1002178813210")  # ✅ string, not int  
DEX_API_BASE = "https://api.dexscreener.com/latest/dex/tokens/"
PREFERRED_DEXES = ["raydium", "pumpfun", "bonkswap", "orca", "lifinity", "meteora"]

# --- Setup logging --- #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from telethon.sessions import StringSession

# Try to load session string from environment
SESSION_STRING = os.getenv("SESSION_STRING")

# Create Telethon client
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

bot = Bot(token=BOT_TOKEN)

ROTATING_PROMO_LINES = [
    "<blockquote>🔓 Get Access to Solana's #1 Memecoin Signals Bot\nCatch the Next 10x–100x Before the Crowd 💸</blockquote>",
    "<blockquote>🚀 Join the Bot Trusted by Solana Degens\nNext Call Could Be Your 50x</blockquote>",
    "<blockquote>📈 Real-Time Memecoin Signals\nBefore the Hype, Before the Crowd</blockquote>",
    "<blockquote>💰 Premium Alpha Drops Daily\nSnipers Are Already In</blockquote>",
    "<blockquote>🎯 Spot the Next 100x Early\nOur Bot Already Did</blockquote>",
    "<blockquote>🥇 Solana’s Smartest Signals\nBuilt by Traders, for Traders</blockquote>",
    "<blockquote>⚡️ Don’t Chase Pumps\nCatch the Next One First</blockquote>",
    "<blockquote>📊 Alpha That Prints\nJust Tap In</blockquote>",
    "<blockquote>🧠 Outsmart the Market\nThe Bot Is Already On It</blockquote>",
    "<blockquote>🔥 Next 10x Gem Is Loading\nWill You Catch It?</blockquote>"
]

# Milestone tracking: stores last ATH per token
milestone_db = {}  # Replace with persistent storage in production

# Cache for marketcap values (address → (value, timestamp))
marketcap_cache = {}

# --- Google Sheets setup --- #
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=scopes)
gs = gspread.authorize(creds)
sheet = gs.open_by_key(GOOGLE_SHEET_ID).sheet1
from telethon.sessions import StringSession

SESSION_STRING = os.getenv("SESSION_STRING")  # New simplified variable

if not SESSION_STRING:
    raise ValueError("SESSION_STRING not set in environment.")
from telethon.sessions import StringSession

# Try to load SESSION_STRING from env
SESSION_STRING = os.getenv("SESSION_STRING")

# Optional fallback to session_b64.txt (for local use)
if not SESSION_STRING:
    b64_path = "session_b64.txt"
    if os.path.exists(b64_path):
        with open(b64_path, "r") as f:
            try:
                SESSION_STRING = base64.b64decode(f.read().strip()).decode()
                logger.info("✅ Loaded SESSION_STRING from session_b64.txt")
            except Exception as e:
                logger.error(f"❌ Failed to decode session_b64.txt: {e}")
    if not SESSION_STRING:
        raise ValueError("❌ SESSION_STRING not set and no session_b64.txt fallback found.")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# --- Keep-Alive Web Server for Replit + UptimeRobot ---
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# Track recently sent milestones to avoid duplicate messages
sent_milestones = set()

# Send regular text message with inline buttons
async def send_bot_message(text, buttons):
    reply_markup = InlineKeyboardMarkup(buttons)  # ✅ Build markup safely

    try:
        logger.info(f"Sending message to chat_id: {PUBLIC_CHANNEL}")
        await bot.send_message(
            chat_id=PUBLIC_CHANNEL,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        logger.info("✅ Message sent.")
    except Exception as e:
        logger.error(f"❌ Failed to send bot message: {e}")


# Get GIF path based on milestone value (e.g., 3.5 → X3+.gif)
def get_milestone_gif_path(x_value):
    x_floor = int(math.floor(x_value))
    return f"media/X{x_floor}+.mp4"  # Example: media/X3+.mp4

# Send milestone GIF + caption + button
async def send_bot_milestone_message(symbol, call_mc, ath_mc, chain, ath_x):
    previous_ath = milestone_db.get(symbol)
    is_update = previous_ath is not None and ath_x > previous_ath

    loop = asyncio.get_event_loop()
    gif_path = get_milestone_gif_path(ath_x)

    buttons = [
        [InlineKeyboardButton("📡 Get Premium Signals", url="https://t.me/onlysubsbot?start=bXeGHtzWUbduBASZemGJf")],
        [InlineKeyboardButton("🔥 Latest Top Wins", url="https://t.me/solana100xcall/4046")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    headline = f"${symbol} HIT 💎{ath_x:.1f}X💎 AFTER CALL"
    promo_line = random.choice(ROTATING_PROMO_LINES)

    caption_parts = [
        headline,
        f"🟢 The Bot Called It At: <b>{abbreviate_number(int(call_mc))}</b> MC\n"
        f"📈 ATH: <b>{abbreviate_number(int(ath_mc))}</b> | Chain: {chain.capitalize()}",
        promo_line
    ]

    if is_update:
        caption_parts.insert(0, "🔥UPDATE🔥")

    caption = "\n\n".join(caption_parts)

    try:
        if not os.path.exists(gif_path):
            logger.warning(f"⚠️ Animation not found for {symbol} ({ath_x:.1f}x). Sending fallback text message.")

            fallback_message = "\n\n".join(caption_parts)
            await send_bot_message(fallback_message, buttons)
            milestone_db[symbol] = ath_x
            return

        with open(gif_path, "rb") as gif_file:
            await bot.send_animation(
                chat_id=PUBLIC_CHANNEL,
                animation=gif_file,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        logger.info(f"✅ Milestone animation sent for {symbol} ({ath_x}x) - Path: {gif_path}")
        milestone_db[symbol] = ath_x

    except Exception as e:
        logger.error(f"❌ Failed to send milestone animation for {symbol} ({ath_x:.1f}x): {e}")
        logger.warning("⚠️ Falling back to text message.")
        await send_bot_message(caption, buttons)

# --- Helper function to extract token info --- #
def normalize_call_mc(mc_str):
    try:
        if mc_str.endswith("K"):
            return str(float(mc_str[:-1]) * 1_000)
        elif mc_str.endswith("M"):
            return str(float(mc_str[:-1]) * 1_000_000)
        elif mc_str.endswith("B"):
            return str(float(mc_str[:-1]) * 1_000_000_000)
        return mc_str  # fallback if no suffix
    except:
        return "0"

def extract_token_info(text):
    # Extract address
    address_match = re.search(r"[A-HJ-NP-Za-km-z1-9]{32,44}", text)
    address = address_match.group(0) if address_match else None
    if not address:
        logger.warning("⚠️ Address not found")

    # Extract symbol
    symbol_match = re.search(r"\(\$(\w+)\)", text)
    symbol = symbol_match.group(1) if symbol_match else None
    if not symbol:
        logger.warning("⚠️ Symbol not found")

    # Extract chain (e.g., #SOL)
    chain_match = re.search(r"#(\w+)", text)
    chain = chain_match.group(1).lower() if chain_match else "solana"  # default fallback

    # Extract Market Cap (MC)
    mc_match = re.search(r"├ MC:\s*\$([\d\.]+[KMB]?)", text)
    call_mc_raw = mc_match.group(1) if mc_match else "0"
    call_mc = normalize_call_mc(call_mc_raw)

    # Return only if essential parts are found
    if address and symbol:
        logger.info(f"✅ Extracted: {address}, {symbol}, MC: {call_mc}")
        return address, symbol, chain, call_mc
    else:
        logger.warning("⚠️ No token info extracted.")
        return None

# --- Utility Functions --- #
def abbreviate_number(num):
    if num >= 1_000_000_000:
        return f"${num / 1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"${num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"${num / 1_000:.1f}k"
    else:
        return f"${num}"

# Save to Google Sheet
def update_sheet(address, symbol, chain, call_mc):
    row = [address, symbol, chain, call_mc, "1.0", "0", "1.0"]  # Set "Last Posted X" = 1.0 to match the initial Last X
    sheet.append_row(row)
    logger.info(f"✅ Saved to sheet: {symbol}, {address}")

# --- Fetch Data From Sheet --- #
def fetch_tokens():
    raw_rows = sheet.get_all_records()
    tokens = []

    for row in raw_rows:
        try:
            token = {
                "contract_address": row.get("Token Address", "").strip(),
                "symbol": row.get("Token Symbol", "").strip(),
                "chain": row.get("Chain", "").strip(),
                "mc_call": float(str(row.get("Call MC (USD)", "0")).replace(",", "").replace("$", "")),
                "last_x": float(str(row.get("Last X", "1.0")).strip()),
                "ath_mc": float(str(row.get("ATH MC", "0")).strip()),
                "last_posted_x": float(str(row.get("Last Posted X", "0")).strip()),
            }
            tokens.append(token)
        except Exception as e:
            logger.warning(f"⚠️ Skipping malformed token row: {e}")

    return tokens

# --- Fetch Current MarketCap from DexScreener API --- #
def get_current_marketcap(contract_address):
    try:
        now = time.time()

        # Return cached result if it's less than 5 minutes old
        if contract_address in marketcap_cache:
            cached_value, cached_time = marketcap_cache[contract_address]
            if now - cached_time < 60:  
                logger.debug(f"⏪ Using cached marketcap for {contract_address}")
                return cached_value

        # Fetch fresh data from DexScreener
        url = f"{DEX_API_BASE}{contract_address}"
        res = requests.get(url, timeout=10)
        
        if res.status_code != 200:
            logging.warning(f"DexScreener API error for {contract_address}: HTTP {res.status_code}")
            return 0
            
        data = res.json()
        pairs = data.get("pairs", [])
        if not pairs:
            logging.warning(f"No pairs found for {contract_address} in DexScreener response")
            return 0

        valid_pairs = [p for p in pairs if p.get("dexId", "") in PREFERRED_DEXES]

        if valid_pairs:
            sorted_pairs = sorted(valid_pairs, key=lambda x: x.get("updatedAt", 0), reverse=True)
            selected_pair = sorted_pairs[0]
        else:
            logging.warning(f"No valid pairs on preferred DEXes for {contract_address}. Found DEXes: {[p.get('dexId') for p in pairs]}")
            sorted_pairs = sorted(pairs, key=lambda x: x.get("updatedAt", 0), reverse=True)
            selected_pair = sorted_pairs[0]

        mc = selected_pair.get("marketCap") or selected_pair.get("fdv")
        return float(mc) if mc else 0

    except Exception as e:
        logging.warning(f"Error fetching marketcap for {contract_address}: {e}")
        return 0

# --- Update Sheet Row Safely with Rate Limiting --- #
async def update_milestone_row(index, new_x, new_ath, new_posted_x=None):
    def normalize_float(value, precision=2):
        try:
            return f"{float(value):.{precision}f}"
        except (ValueError, TypeError):
            return ""

    try:
        row_number = index + 2
        current_values = sheet.row_values(row_number)

        current_x = normalize_float(current_values[4]) if len(current_values) > 4 else ""
        current_ath = normalize_float(current_values[5], 0) if len(current_values) > 5 else ""
        current_posted_x = normalize_float(current_values[6]) if len(current_values) > 6 else ""

        new_x_norm = normalize_float(new_x)
        new_ath_norm = normalize_float(new_ath, 0)
        new_posted_x_norm = normalize_float(new_posted_x) if new_posted_x is not None else None

        updates_needed = False

        if current_x != new_x_norm:
            sheet.update_cell(row_number, 5, new_x_norm)
            updates_needed = True

        if current_ath != new_ath_norm:
            sheet.update_cell(row_number, 6, new_ath_norm)
            updates_needed = True

        if new_posted_x_norm is not None and current_posted_x != new_posted_x_norm:
            sheet.update_cell(row_number, 7, new_posted_x_norm)
            updates_needed = True

        if updates_needed:
            logger.info(f"📝 Updated row {row_number}: Last X = {new_x_norm}, ATH MC = {new_ath_norm}, Last Posted X = {new_posted_x_norm}")
            await asyncio.sleep(0.8)  # Rate limit safety
        else:
            logger.debug(f"⏸ No update needed for row {row_number}")

    except Exception as e:
        logger.error(f"❌ Failed to update row {index + 2}: {e}")

# --- Milestone Monitor (Dynamic) --- #
async def monitor_milestones():
    logger.info("📡 Starting milestone monitor...")

    while True:
        try:
            logger.info("🔄 Checking tokens for milestone updates...")
            all_rows = sheet.get_all_values()
            header = all_rows[0]
            data_rows = all_rows[1:]

            for i, row in enumerate(data_rows):
                try:
                    address = row[0].strip()
                    symbol = row[1]
                    chain = row[2]
                    call_mc = float(row[3].replace(",", "").replace("$", ""))
                    last_x = float(row[4]) if len(row) > 4 and row[4] else 0
                    ath_mc = float(row[5]) if len(row) > 5 and row[5] else 0
                    last_posted_x = float(row[6]) if len(row) > 6 and row[6] else 0

                    if not address or call_mc == 0:
                        continue

                    await asyncio.sleep(0.8)  # Rate limit delay
                    current_mc = get_current_marketcap(address)
                    logger.info(f"Processing {symbol}: call_mc={call_mc}, current_mc={current_mc}, last_x={last_x}, ath_mc={ath_mc}")

                    if current_mc == 0:
                        continue

                    # Update ATH market cap if new high
                    if current_mc > ath_mc:
                        ath_mc = current_mc
                        await update_milestone_row(i, str(last_x), str(int(ath_mc)), None)
                        logger.info(f"📈 New ATH for {symbol}: ${int(ath_mc):,}")

                    ath_x = round(ath_mc / call_mc, 2)

                    # If this ATH X is higher than the last posted one, it's a new milestone
                    ath_x = ath_mc / call_mc
                    rounded_ath_x = round(ath_x, 1)
                    rounded_last_posted_x = round(last_posted_x, 1)

                    if rounded_ath_x >= 1.5 and rounded_ath_x > rounded_last_posted_x:
                        try:
                            await send_bot_milestone_message(
                                symbol=symbol,
                                call_mc=call_mc,
                                ath_mc=ath_mc,
                                chain=chain,
                                ath_x=rounded_ath_x
                            )
                            await update_milestone_row(
                                index=i,
                                new_x=rounded_ath_x,
                                new_ath=int(ath_mc),
                                new_posted_x=rounded_ath_x
                            )
                            logger.info(f"📢 Posted {'🔥UPDATE🔥' if last_posted_x > 0 else 'NEW'} milestone for {symbol}: {rounded_ath_x}x")
                        except Exception as e:
                            logger.error(f"❌ Failed to post milestone for {symbol}: {e}")

                except Exception as e:
                    logger.error(f"⚠️ Error processing row {i + 2}: {e}")

        except Exception as e:
            logger.error(f"❌ Error during milestone check: {e}")

        logger.info("🔁 Sleeping 5 minutes before next check...")
        await asyncio.sleep(300)  # 5 minutes pause


# --- Message handler --- #
@client.on(events.NewMessage(chats=GROUP_ID))
async def handle_message(event):
    try:
        text = event.message.message

        # 🔍 Log the raw message
        logger.info(f"📨 Incoming message:\n{text}")

        # Extract token info
        token_info = extract_token_info(text)

        if token_info:
            address, symbol, chain, call_mc = token_info

            # ✅ Now call the sheet updater
            update_sheet(address, symbol, chain, call_mc)

    except Exception as e:
        logger.error(f"❌ Error in message handler: {e}")

# --- Run the client --- #
async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print("Client is not authorized. Upload the session file.")
        exit(1)
    client.loop.create_task(monitor_milestones())
    logger.info("🤖 Bot is running...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    keep_alive()
    client.loop.run_until_complete(main())
