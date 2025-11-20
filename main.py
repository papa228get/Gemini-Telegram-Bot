import asyncio
import os
import logging
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

# ВАЖНО: Импортируем web и ClientSession явно
from aiohttp import web, ClientSession

# Библиотеки для Телеграма
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, CommandObject

# Библиотека для Gemini
import google.generativeai as genai

# 1. Загрузка ключей
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
gemini_key = os.getenv("GEMINI_API_KEY")
hf_key = os.getenv("HF_API_KEY")

# API Художника
HF_API_URL = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
HF_HEADERS = {"Authorization": f"Bearer {hf_key}"}

# 2. Настройка Gemini
genai.configure(api_key=gemini_key)
model = genai.GenerativeModel(
    'gemini-2.0-flash',
    system_instruction=r"Ты — помощник в Telegram. Используй синтаксис Telegram MarkdownV2. "
                       r"ОБЯЗАТЕЛЬНО экранируй спецсимволы: . ! - ( ) [ ] ~ > # + = | { } обратным слэшем (например \!)."
)

# 3. Настройка бота
bot = Bot(token=bot_token)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- Вспомогательные функции ---
async def send_safe_message(message: types.Message, text: str):
    if len(text) > 4000: text = text[:4000] + "..."
    try: await message.answer(text, parse_mode="MarkdownV2")
    except Exception: await message.answer(text)

# --- Веб-сервер для Render ---
async def health_check(request):
    return web.Response(text="Bot is alive and drawing!")

async def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- Рисование --
async def query_image_api(prompt_text):
    async with ClientSession() as session:
        try:
            async with session.post(HF_API_URL, headers=HF_HEADERS, json={"inputs": prompt_text}, timeout=30) as response:
                if response.status != 200:
                    return None, f"Ошибка API: {response.status}"
                return await response.read(), None
        except Exception as e:
            return None, str(e)

# --- Обработчики ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я вижу картинки и умею рисовать (/draw запрос).")

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Напиши: `/draw что нарисовать`", parse_mode="Markdown")
        return
    
    status = await message.answer("🎨 Рисую...")
    img_bytes, err = await query_image_api(command.args)
    
    if err:
        await status.edit_text(f"Ошибка: {err}")
        return
        
    await message.answer_photo(types.BufferedInputFile(img_bytes, "img.png"), caption=f"🎨 {command.args}")
    await status.delete()

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    try:
        f = await bot.download(message.photo[-1])
        f.seek(0)
        response = model.generate_content([message.caption or "Что это?", Image.open(f)])
        await send_safe_message(message, response.text)
    except Exception as e:
        await message.answer(str(e))

@dp.message(F.text)
async def handle_message(message: types.Message):
    try:
        response = model.generate_content(message.text)
        await send_safe_message(message, response.text)
    except Exception as e:
        await message.answer(str(e))

async def main():
    await asyncio.gather(dp.start_polling(bot), start_web_server())

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
