import asyncio
import os
import logging
import aiohttp # Для веб-сервера и запросов к художнику
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO # Для работы с файлами в памяти

# Библиотеки для Телеграма
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, CommandObject

# Библиотека для Gemini
import google.generativeai as genai

# 1. Загрузка ключей
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
gemini_key = os.getenv("GEMINI_API_KEY")
hf_key = os.getenv("HF_API_KEY") # Ключ художника (Hugging Face)

# API-адрес модели-художника (Stable Diffusion XL - отличная и быстрая)
HF_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
# Заголовки для авторизации
HF_HEADERS = {"Authorization": f"Bearer {hf_key}"}

# 2. Настройка Gemini (Мозг и Глаза)
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
    """Безопасная отправка текста (защита от сбоев Markdown)"""
    if len(text) > 4000: text = text[:4000] + "..."
    try: await message.answer(text, parse_mode="MarkdownV2")
    except Exception: await message.answer(text)

# --- Веб-сервер для Render (Health Check) ---
async def health_check(request): 
    return aiohttp.web.Response(text="Bot is alive and drawing!")

async def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app = aiohttp.web.Application()
    app.router.add_get('/', health_check)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- Функция рисования (Запрос к Hugging Face) ---
async def query_image_api(prompt_text):
    async with aiohttp.ClientSession() as session:
        try:
            # Отправляем запрос на сервера Hugging Face
            async with session.post(HF_API_URL, headers=HF_HEADERS, json={"inputs": prompt_text}, timeout=30) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return None, f"Ошибка API ({response.status}): {error_text}"
                
                # Если успех — получаем байты картинки
                image_bytes = await response.read()
                return image_bytes, None
        except Exception as e:
            return None, str(e)

# --- Обработчики Бота ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я Gemini Pro Bot.\n\n"
        "🤖 **Чат:** Пиши любой вопрос.\n"
        "👁 **Зрение:** Пришли фото, я расскажу что там.\n"
        "🎨 **Художник:** Напиши `/draw Текст` (например: `/draw кот в космосе`), и я нарисую.",
        parse_mode="Markdown"
    )

# 🎨 Команда /draw
@dp.message(Command("draw"))
async def cmd_draw(message: types.Message, command: CommandObject):
    if command.args is None:
        await message.answer("Напиши, что нарисовать. Пример:\n`/draw футуристический город`", parse_mode="Markdown")
        return

    prompt = command.args
    await bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
    status_msg = await message.answer("🎨 Рисую... Это займет около 10-15 секунд.")

    image_bytes, error = await query_image_api(prompt)

    if error:
        await status_msg.edit_text(f"Не удалось нарисовать 😢\nСервер перегружен или ошибка ключа.\nДетали: {error}")
        return

    # Отправляем картинку из памяти
    photo_file = types.BufferedInputFile(image_bytes, filename="image.png")
    await message.answer_photo(photo_file, caption=f"🎨 *{prompt}*", parse_mode="Markdown")
    await status_msg.delete()

# 👁 Обработка ФОТО
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
    try:
        # Скачиваем и "перематываем" файл
        photo = message.photo[-1]
        file_io = await bot.download(photo)
        file_io.seek(0)
        
        img = Image.open(file_io)
        user_text = message.caption if message.caption else "Что на этом изображении? Опиши подробно."
        
        response = model.generate_content([user_text, img])
        await send_safe_message(message, response.text)
    except Exception as e:
        await message.answer(f"Ошибка зрения: {str(e)}")

# 🗣 Обработка ТЕКСТА
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
    # Запускаем параллельно: Бота и Веб-сервер (для Render)
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")