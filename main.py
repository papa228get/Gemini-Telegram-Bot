import asyncio
import os
import logging
from dotenv import load_dotenv

# Библиотеки для Телеграма
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# Библиотека для Gemini
import google.generativeai as genai

# 1. Загружаем ключи из файла .env
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
gemini_key = os.getenv("GEMINI_API_KEY")

# 2. Настройка Gemini
genai.configure(api_key=gemini_key)
# Используем модель gemini-1.5-flash (она быстрая и бесплатная)
model = genai.GenerativeModel('gemini-2.0-flash')

# 3. Настройка Бота
bot = Bot(token=bot_token)
dp = Dispatcher()

# Включаем логирование, чтобы видеть ошибки в консоли
logging.basicConfig(level=logging.INFO)

# --- Обработчики событий ---

# Команда /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот на базе Google Gemini.\nНапиши мне любой вопрос.")

# Обработка текстовых сообщений
@dp.message(F.text)
async def handle_message(message: types.Message):
    # Отправляем боту статус "печатает...", чтобы пользователь видел активность
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Отправляем запрос в Gemini
        response = model.generate_content(message.text)
        
        # Получаем текст ответа
        bot_answer = response.text
        
        # Telegram имеет лимит на длину сообщения (4096 символов). 
        # Если ответ длинный, его нужно разбивать, но пока отправим как есть (или обрежем).
        if len(bot_answer) > 4000:
            bot_answer = bot_answer[:4000] + "...(ответ обрезан)"
            
        await message.answer(bot_answer)
        
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")

# --- Запуск бота ---
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
