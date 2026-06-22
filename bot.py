import asyncio
import aiohttp
import json
import random
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# --- Configuration ---
BOT_TOKEN = "8985394925:AAGy7qxqTkDvZRbvO8wmtFmvv1-8ivSxBtc"

# --- Proxies ---
PROXIES = [
    
]

logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Headers for the CrownIt request
HEADERS = {
    'User-Agent': "Mozilla/5.0 (Linux; Android 16; RMX5110 Build/BP2A.250605.015) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.7827.91 Mobile Safari/537.36",
    'Accept': "application/json, text/plain, */*",
    'Accept-Encoding': "gzip, deflate, br, zstd",
    'Content-Type': "application/json",
    'sec-ch-ua-platform': "\"Android\"",
    'sec-ch-ua': "\"Android WebView\";v=\"149\", \"Chromium\";v=\"149\", \"Not)A;Brand\";v=\"24\"",
    'sec-ch-ua-mobile': "?1",
    'origin': "https://feedback.crownit.in",
    'x-requested-with': "mark.via.gp",
    'sec-fetch-site': "same-origin",
    'sec-fetch-mode': "cors",
    'sec-fetch-dest': "empty",
    'referer': "https://feedback.crownit.in/lite/onboarding",
    'accept-language': "en-GB,en-US;q=0.9,en;q=0.8",
    'priority': "u=1, i",
    'Cookie': "_ga=GA1.2.1801453703.1781610099; _fbp=fb.1.1781610100333.18439279738495991; _gid=GA1.2.2067272511.1782132012; _gat=1; googtrans=/en/en"
}

def get_main_keyboard():
    keyboard = [
        [KeyboardButton(text="🔍 Check Numbers")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# --- Global HTTP Session for High Concurrency ---
http_session: aiohttp.ClientSession = None

async def on_startup():
    global http_session
    connector = aiohttp.TCPConnector(limit=1000)
    timeout = aiohttp.ClientTimeout(total=15)
    http_session = aiohttp.ClientSession(connector=connector, timeout=timeout)

async def on_shutdown():
    global http_session
    if http_session:
        await http_session.close()

# --- CrownIt Checking Logic ---
async def check_crownit_number(phone_no: str, max_retries: int = 5) -> dict:
    url = "https://feedback.crownit.in/api/get/term-and-cond-status"
    payload = {"phone_no": phone_no}
    
    last_error = None
    last_proxy = None
    
    for attempt in range(max_retries):
        proxy = random.choice(PROXIES) if PROXIES else None
        last_proxy = proxy
        try:
            async with http_session.post(url, json=payload, headers=HEADERS, proxy=proxy) as response:
                if response.status == 200:
                    data = await response.json()
                    return {"success": True, "data": data, "proxy": proxy, "phone_no": phone_no}
                else:
                    last_error = f"HTTP {response.status}"
                    continue
        except Exception as e:
            last_error = str(e)
            continue
            
    return {"success": False, "error": last_error, "proxy": last_proxy, "phone_no": phone_no}

# --- Handlers ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name
    welcome_text = (
        f"👑 <b>Welcome {user_name}!</b>\n\n"
        "⚡️ Send up to 10 numbers to check CrownIt status."
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@dp.message(F.text == "🔍 Check Numbers")
async def handle_check_numbers_btn(message: types.Message):
    await message.answer("📝 <b>Send me any 10-digit number or a list of up to 10 numbers to check!</b>")

@dp.message(F.text)
async def process_number(message: types.Message):
    text = message.text.strip()
    
    # Extract all 10-digit numbers using regex
    numbers = re.findall(r'\b\d{10}\b', text)
    numbers = list(dict.fromkeys(numbers))  # remove duplicates
    
    if not numbers:
        await message.answer("⚠️ <b>No valid 10-digit numbers found.</b>\nPlease send numbers like <code>9876543210</code>.")
        return

    if len(numbers) > 10:
        await message.answer("⚠️ <b>Too many numbers!</b>\nPlease send a maximum of 10 numbers at a time for bulk checking.")
        return

    processing_msg = await message.answer(f"🔄 <b>Ultimate PK 🚀 Checker Running...</b>\nChecking {len(numbers)} number(s). Please wait! ⚡️")

    # Run checks concurrently with live updates
    tasks = [asyncio.create_task(check_crownit_number(num)) for num in numbers]
    
    registered = []
    unregistered = []
    errors = []

    total_nums = len(numbers)
    completed = 0

    for coro in asyncio.as_completed(tasks):
        result = await coro
        num = result['phone_no']
        if result["success"]:
            data = result["data"]
            if "showTerms" in data:
                if data["showTerms"]:
                    registered.append(num)
                else:
                    unregistered.append(num)
            else:
                errors.append(f"{num} (Unexpected response)")
        else:
            errors.append(f"{num} (Error: {result['error']})")
            
        completed += 1
        live_text = f"🔄 <b>Ultimate PK 🚀 Checker Running...</b>\nProgress: {completed}/{total_nums} ⚡️\n\n"
        if unregistered:
            live_text += f"✅ Fresh: {len(unregistered)}\n"
        if registered:
            live_text += f"❌ Registered: {len(registered)}\n"
        if errors:
            live_text += f"⚠️ Errors: {len(errors)}\n"
            
        try:
            await processing_msg.edit_text(live_text)
        except Exception:
            pass

    # Format the final response
    response_text = "👑 <b>ULTIMATE PK 🚀 CROWNIT REPORT</b> 👑\n\n"
    
    if unregistered:
        response_text += "✅ <b>NOT REGISTERED (FRESH):</b>\n"
        for num in unregistered:
            response_text += f"<code>{num}</code>\n"
        response_text += "\n"
        
    if registered:
        response_text += "❌ <b>ALREADY REGISTERED:</b>\n"
        for num in registered:
            response_text += f"<code>{num}</code>\n"
        response_text += "\n"
        
    if errors:
        response_text += "⚠️ <b>ERRORS:</b>\n"
        for err in errors:
            response_text += f"<code>{err}</code>\n"
            
    response_text += "━━━━━━━━━━━━━━━━━━\n"
    response_text += "🚀 <b>Powered by Ultimate PK 🚀</b>"

    await processing_msg.edit_text(response_text)


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    print("Starting Ultimate PK 🚀 CrownIt Checker Bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
