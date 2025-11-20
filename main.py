import asyncio
import os
import logging
from dotenv import load_dotenv

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

# Используем системную инструкцию, чтобы приучить ИИ к формату Telegram MarkdownV2
model = genai.GenerativeModel(
    'gemini-2.0-flash',
    system_instruction="Ты — помощник в Telegram. Используй синтаксис Telegram MarkdownV2 для форматирования. "
                       "Жирный: *text*, Курсив: _text_, Код: `text`. "
                       "ОБЯЗАТЕЛЬНО экранируй спецсимволы: . ! - ( ) [ ] ~ > # + = | { } обратным слэшем (например \!)."
)

# 3. Настройка бота
bot = Bot(token=bot_token)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# --- Обработчики ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот на базе Gemini 2.0.\nСпрашивай меня о чем угодно.")

@dp.message(F.text)
async def handle_message(message: types.Message):
    # Показываем статус "печатает..."
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Генерируем ответ
        response = model.generate_content(message.text)
        bot_answer = response.text
        
        # Обрезаем, если слишком длинно (лимит ТГ ~4096)
        if len(bot_answer) >
