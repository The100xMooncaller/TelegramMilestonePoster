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
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask
from threading import Thread

# --- Load environment variables --- #
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
GROUP_ID = int(os.getenv("PRIVATE_GROUP_ID"))
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- Handle dynamic Google credentials from environment variable --- #
google_json = os.getenv("GOOGLE_SHEET_JSON")
if google_json:
    with open("credentials.json", "w") as f:
        f.write(google_json)
    CREDENTIALS_PATH = "credentials.json"
else:
    raise ValueError("Missing GOOGLE_SHEET_JSON environment variable")

# --- Setup logging --- #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
bot = Bot(token=BOT_TOKEN)

# --- Constants --- #
MILESTONES = [1.5, 2, 3, 6, 9, 11, 14, 20, 23, 30, 33, 39, 44, 55, 63, 66, 69,
              93, 96, 99, 100, 111, 200, 222, 300, 333, 369, 444, 555, 639,
              666, 693, 936, 963, 999, 1000, 1111]
PUBLIC_CHANNEL = "@solana100xcall"
DEX_API_BASE = "https://api.dexscreener.com/latest/dex/tokens/"
PREFERRED_DEXES = ["raydium", "pumpfun", "bonkswap", "orca", "lifinity", "meteora"]  

ROTATING_LINK_CAPTIONS = [
    "🤑 300 Killer Wallets. Copy → Win.",
    "🚨 Top 300 Solana Wallets. DAILY Printing.",
    "🧠 Smart Money Printing. Keep going or stay poor.",
    "🚀 It's happening NOW. Track the wallets.",
    "💸 Non-stop wallet printing. Are you in or what?",
    "👑 They print. You follow. You win.",
    "🧠 Smarter wallets. It's silly not to follow.",
    "🎯 Wallets that never run out. Yours now.",
    "📈 Print like a pro. We have the file."
]

# Cache for marketcap values (address → (value, timestamp))
marketcap_cache = {}

# --- Google Sheets setup --- #
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=scopes)
gs = gspread.authorize(creds)
sheet = gs.open_by_key(GOOGLE_SHEET_ID).sheet1

# --- Telethon client --- #
client = TelegramClient("session_name", API_ID, API_HASH)

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
    loop = asyncio.get_event_loop()
    reply_markup = InlineKeyboardMarkup(buttons)

    try:
        logger.info(f"Sending message to chat_id: {PUBLIC_CHANNEL}")
        logger.info(f"chat_id type: {type(PUBLIC_CHANNEL)}")

        await loop.run_in_executor(
            None,
            partial(
                bot.send_message,
                chat_id=PUBLIC_CHANNEL,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
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
    loop = asyncio.get_event_loop()
    gif_path = get_milestone_gif_path(ath_x)

    buttons = [
        [InlineKeyboardButton("📡 Get Premium Signals", url="https://t.me/onlysubsbot?start=bXeGHtzWUbduBASZemGJf")],
        [InlineKeyboardButton("🔥 Latest Top Wins", url="https://t.me/solana100xcall/4046")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    rotating_link_text = random.choice(ROTATING_LINK_CAPTIONS)
    
    caption = (
        f"${symbol} HIT 💎{ath_x:.1f}X💎 AFTER CALL\n\n"
        f"🟢 Bot Called It at: <b>{abbreviate_number(int(call_mc))}</b> MC\n"
        f"📈 ATH: <b>{abbreviate_number(int(ath_mc))}</b> | Chain: {chain.capitalize()}\n\n"
        f"<blockquote>🔓 Get Access to Solana's #1 Memecoin Signals Bot & Catch the Next 10x–100x Before the Crowd 💸</blockquote>\n\n"
        f"<a href='https://t.me/SmartWalletsSOLBot'>{rotating_link_text}</a>"
    )

    gif_path = get_milestone_gif_path(ath_x)

    try:
        if not os.path.exists(gif_path):
            logger.warning(f"⚠️ Animation not found for {symbol} ({ath_x:.1f}x). Sending fallback text message.")

            message = (
                f"${symbol} HIT 💎{ath_x:.1f}X💎 AFTER CALL\n\n"
                f"🟢 Bot Called It at: <b>{abbreviate_number(int(call_mc))}</b> MC\n"
                f"📈 ATH: <b>{abbreviate_number(int(ath_mc))}</b> | Chain: {chain.capitalize()}\n\n"
                f"<blockquote>🔓 Get Access to Solana's #1 Memecoin Signals Bot & Catch the Next 10x–100x Before the Crowd 💸</blockquote>\n\n"
                f"<a href='https://t.me/SmartWalletsSOLBot'>📊 ADD 300 alpha wallets to your Solana tracker</a>"
            )

            buttons = [[
                InlineKeyboardButton("📡 Get Premium Signals", url="https://t.me/onlysubsbot?start=bXeGHtzWUbduBASZemGJf")
            ]]

            await send_bot_message(message, buttons)
            return

        with open(gif_path, "rb") as gif_file:
            gif_bytes = gif_file.read()

        await loop.run_in_executor(
            None,
            partial(
                bot.send_animation,
                chat_id=PUBLIC_CHANNEL,
                animation=open(gif_path, "rb"),  # ✅ Direct file path
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        )
        logger.info(f"✅ Milestone animation sent for {symbol} - Path: {gif_path}")
    except Exception as e:
        logger.error(f"❌ Failed to send milestone animation for {symbol} ({ath_x:.1f}x): {e}")
        logger.warning("⚠️ Falling back to text message.")

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
        token = {
            "contract_address": row.get("Token Address", "").strip(),
            "symbol": row.get("Token Symbol", "").strip(),
            "chain": row.get("Chain", "").strip(),
            "mc_call": row.get("Call MC (USD)", 0),
            "last_x": row.get("Last X", "1.0").strip(),
            "ath_mc": row.get("ATH MC", "0").strip(),
        }
        tokens.append(token)
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

        # Cache the result
        marketcap_cache[contract_address] = (marketcap, now)

        return marketcap

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
            await asyncio.sleep(0.5)  # Rate limit safety
        else:
            logger.debug(f"⏸ No update needed for row {row_number}")

    except Exception as e:
        logger.error(f"❌ Failed to update row {index + 2}: {e}")

# --- Milestone Monitor --- #
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

                    await asyncio.sleep(0.8)  # Delay to reduce API rate (1-2s per request is safe)
                    current_mc = get_current_marketcap(address)
                    logger.info(f"Processing {symbol}: call_mc={call_mc}, current_mc={current_mc}, last_x={last_x}, ath_mc={ath_mc}")

                    if current_mc == 0:
                        continue
      
                    if current_mc > ath_mc:
                        ath_mc = current_mc
                        await update_milestone_row(i, str(last_x), str(int(ath_mc)), None)
                        logger.info(f"📈 New ATH for {symbol}: ${int(ath_mc):,}")

                    ath_x = ath_mc / call_mc
                    milestone = next((m for m in MILESTONES if ath_x >= m and m > last_posted_x), None)

                    milestone_key = f"{symbol}-{milestone}"

                    if milestone and milestone > last_posted_x:
                        try:
                            await send_bot_milestone_message(symbol, call_mc, ath_mc, chain, ath_x)
                            await update_milestone_row(i, str(milestone), str(int(ath_mc)), str(milestone))
                            logger.info(f"📢 Posted new milestone for {symbol}: {milestone}x")
                        except Exception as e:
                            logger.error(f"❌ Failed to post milestone for {symbol}: {e}")

                except Exception as e:
                    logger.error(f"Error processing row {i + 2}: {e}")

        except Exception as e:
            logger.error(f"❌ Error during milestone check: {e}")

        logger.info("🔁 Sleeping 5 minutes before next check...")
        await asyncio.sleep(300)  # Check every 5 minutes

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
    await client.start(phone=PHONE_NUMBER)
    client.loop.create_task(monitor_milestones())
    logger.info("🤖 Bot is running...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    keep_alive()
    client.loop.run_until_complete(main())
