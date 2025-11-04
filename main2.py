import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Update, Message
from aiogram.filters import Command
from aiohttp import web

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Команда /start
@dp.message(Command("start"))
async def start(message: Message):
    await bot.send_message(message.from_user.id, "Привет! Бот работает.")

# Обработка любого текста
@dp.message()
async def echo(message: Message):
    await bot.send_message(message.from_user.id, f"Ты написал: {message.text}")

# aiohttp routes
async def handle_webhook(request: web.Request):
    try:
        json_string = await request.text()
        update = Update.model_validate_json(json_string)
        await dp.feed_update(bot, update)
        return web.json_response({"ok": True})
    except Exception as e:
        logging.error(f"Ошибка вебхука: {e}")
        return web.json_response({"ok": False}, status=500)

async def handle_index(request: web.Request):
    return web.Response(text="Bot is running", status=200)

# Webhook setup
async def on_startup(app):
    webhook_url = f"https://picasso-bot-nilp.onrender.com/webhook"  # ⬅️ твой URL
    await bot.set_webhook(webhook_url, drop_pending_updates=True)
    logging.info(f"Webhook установлен: {webhook_url}")

async def on_shutdown(app):
    await bot.delete_webhook()

# Запуск
if __name__ == "__main__":
    app = web.Application()
    app.add_routes([
        web.post('/webhook', handle_webhook),
        web.get('/', handle_index),
    ])
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    port = int(os.getenv("PORT", 8000))
    web.run_app(app, host="0.0.0.0", port=port)
