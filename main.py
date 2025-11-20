import asyncio
import os
import logging
import random # Нужно для генерации seed
from dotenv import load_dotenv
from PIL import Image

# Импортируем библиотеки
from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, CommandObject
import google.generativeai as genai

# 1. Загрузка ключей
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
gemini_key = os.getenv("GEMINI_API_KEY")

# 2. Настройка Gemini (Мозг + Переводчик)
genai.configure(api_key=gemini_key)
model = genai.GenerativeModel(
    'gemini-2.0-flash',
    system_instruction=r"Ты — помощник в Telegram. Твоя цель — быть полезным."
)

# 3. Настройка бота
bot = Bot(token=bot_token)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- Веб-сервер для Render ---
async def health_check(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- 🧠 Функция перевода (Gemini помогает художнику) ---
async def translate_prompt_to_english(text):
    try:
        # Просим Gemini перевести запрос на английский для лучшей генерации
        prompt = f"Translate this text to English specifically for an AI image generator prompt. Output ONLY the English translation, nothing else. Text: {text}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return text # Если перевод сломался, возвращаем как было

# --- 🎨 Рисование (Pollinations) ---
async def get_image_from_pollinations(prompt_text):
    seed = random.randint(0, 100000)
    # Используем модель Flux (лучшее качество)
    url = f"https://image.pollinations.ai/prompt/{prompt_text}?width=1280&height=720&seed={seed}&model=flux"
    
    async with ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None, f"Ошибка сервера: {response.status}"
                return await response.read(), None
        except Exception as e:
            return None, str(e)

# --- Обработчики ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Я Gemini Bot.\n"
        "💬 **Чат:** Пиши любой вопрос.\n"
        "👁 **Зрение:** Пришли фото.\n"
        "🎨 **Рисование:** Пиши `/draw Твой Запрос` (я сам переведу его на английский)."
    )

@dp.message(Command("draw"))
async def cmd_draw(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Пример: `/draw киберпанк город`")
        return
    
    status = await message.answer(f"🇬🇧 Перевожу запрос и рисую...")
    
    # 1. Сначала переводим на английский
    english_prompt = await translate_prompt_to_english(command.args)
    
    # 2. Рисуем по английскому запросу
    img_bytes, err = await get_image_from_pollinations(english_prompt)
    
    if err:
        await status.edit_text(f"Ошибка: {err}")
        return
        
    await message.answer_photo(
        types.BufferedInputFile(img_bytes, "img.png"), 
        caption=f"🎨 *{command.args}*\n(Prompt: {english_prompt})",
        parse_mode="Markdown"
    )
    await status.delete()

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    try:
        await bot.send_chat_action(message.chat.id, "typing")
        f = await bot.download(message.photo[-1])
        response = model.generate_content(["Что на фото?", Image.open(f)])
        await message.answer(response.text)
    except Exception as e:
        await message.answer(str(e))

@dp.message(F.text)
async def handle_message(message: types.Message):
    try:
        # Используем MarkdownV2 только если уверены, но для простоты тут обычный текст
        await bot.send_chat_action(message.chat.id, "typing")
        response = model.generate_content(message.text)
        await message.answer(response.text) 
    except Exception as e:
        await message.answer(str(e))

async def main():
    await asyncio.gather(dp.start_polling(bot), start_web_server())

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass