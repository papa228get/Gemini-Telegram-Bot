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

# Используем raw-строку (r""), чтобы Python не ругался на слэши
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

# --- Обработчики ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я снова в строю (версия 2.0 Fixed).\nЗадавай вопросы!")

@dp.message(F.text)
async def handle_message(message: types.Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        response = model.generate_content(message.text)
        bot_answer = response.text
        
        # ИСПРАВЛЕННАЯ СТРОКА 52 (добавили 4000 и двоеточие)
        if len(bot_answer) > 4000:
            bot_answer = bot_answer[:4000] + "..."
            
        # --- ГИБРИДНАЯ ОТПРАВКА ---
        try:
            await message.answer(bot_answer, parse_mode="MarkdownV2")
        except Exception as e:
            print(f"Ошибка MarkdownV2: {e}. Отправляю чистый текст.")
            await message.answer(bot_answer)
            
    except Exception as e:
        await message.answer(f"Ошибка генерации: {str(e)}")

# --- Запуск ---
async def main():
    print("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
