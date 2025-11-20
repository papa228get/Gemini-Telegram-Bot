import asyncio
import os
import logging
import io  # Для работы с файлами в памяти
from dotenv import load_dotenv
from PIL import Image # Библиотека для обработки картинок

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

# --- Вспомогательная функция отправки ---
async def send_safe_message(message: types.Message, text: str):
    """Отправляет сообщение с попыткой MarkdownV2, при ошибке шлет обычный текст"""
    if len(text) > 4000:
        text = text[:4000] + "..."
    try:
        await message.answer(text, parse_mode="MarkdownV2")
    except Exception:
        await message.answer(text)

# --- Обработчики ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я вижу и слышу (текст).\nПришли мне фото и спроси, что на нем!")

# Обработка КАРТИНОК
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
    
    try:
        # 1. Скачиваем фото из Телеграма в память (не сохраняя на диск)
        photo_file = await bot.download(message.photo[-1])
        img = Image.open(photo_file)
        
        # 2. Берем подпись к фото (если есть) или придумываем вопрос
        user_text = message.caption if message.caption else "Опиши, что на этом изображении?"
        
        # 3. Отправляем картинку + текст в Gemini
        response = model.generate_content([user_text, img])
        
        # 4. Отправляем ответ
        await send_safe_message(message, response.text)
        
    except Exception as e:
        await message.answer(f"Ошибка обработки фото: {str(e)}")

# Обработка ТЕКСТА
@dp.message(F.text)
async def handle_message(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = model.generate_content(message.text)
        await send_safe_message(message, response.text)
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")

# --- Запуск ---
async def main():
    print("Бот с функцией Зрения (Vision) запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
