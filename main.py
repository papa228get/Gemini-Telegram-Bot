import asyncio
import os
import logging
from dotenv import load_dotenv
from PIL import Image
from aiohttp import web # Добавляем веб-сервер

# Библиотеки для Телеграма
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# Библиотека для Gemini
import google.generativeai as genai

# 1. Загрузка ключей
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
gemini_key = os.getenv("GEMINI_API_KEY")

# 2. Настройка Gemini
genai.configure(api_key=gemini_key)

model = genai.GenerativeModel(
    'gemini-2.0-flash',
    system_instruction=r"Ты — помощник в Telegram. Используй синтаксис Telegram MarkdownV2. "
                       r"Жирный: *text*, Курсив: _text_, Код: `text`. "
                       r"ОБЯЗАТЕЛЬНО экранируй спецсимволы: . ! - ( ) [ ] ~ > # + = | { } обратным слэшем (например \!)."
)

# 3. Настройка бота
bot = Bot(token=bot_token)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# --- Вспомогательные функции ---
async def send_safe_message(message: types.Message, text: str):
    if len(text) > 4000:
        text = text[:4000] + "..."
    try:
        await message.answer(text, parse_mode="MarkdownV2")
    except Exception:
        await message.answer(text)

# --- Веб-сервер для Render (Health Check) ---
async def health_check(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    # Render сам дает порт через переменную окружения PORT
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    print(f"Web-сервер запущен на порту {port}")
    await site.start()

# --- Обработчики Бота ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я живу в облаке и вижу картинки.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
    try:
        photo_file = await bot.download(message.photo[-1])
        img = Image.open(photo_file)
        user_text = message.caption if message.caption else "Что на этом изображении?"
        response = model.generate_content([user_text, img])
        await send_safe_message(message, response.text)
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")

@dp.message(F.text)
async def handle_message(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = model.generate_content(message.text)
        await send_safe_message(message, response.text)
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")

# --- Главный запуск ---
async def main():
    # Запускаем и бота, и веб-сервер параллельно
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
