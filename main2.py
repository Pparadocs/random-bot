import os
import logging
import requests
import time
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.types import Message
from aiogram.filters import Command
from aiohttp import web

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Стили
STYLES = {
    "конфетти": "candy",
    "мозаика": "mosaic",
    "принцесса дождя": "rain_princess",
    "удни": "udnie",
    "аниме": "anime",
    "ван гог": "van gogh",
    "киберпанк": "cyberpunk",
    "пиксель-арт": "pixel art"
}

# Хранилища
user_style = {}  # {user_id: style_key}

# Вспомогательные функции
async def process_image(message: Message):
    user_id = message.from_user.id
    style_key = user_style.get(user_id)
    if not style_key:
        await bot.send_message(user_id, "Сначала выбери стиль: " + ", ".join(STYLES.keys()))
        return

    await bot.send_message(user_id, "⏳ Обрабатываю... (5–10 сек)")

    photo = message.photo[-1]
    try:
        file = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
    except Exception as e:
        logging.error(f"Ошибка получения файла: {e}")
        await bot.send_message(user_id, "Не удалось загрузить фото. Попробуй снова.")
        return

    try:
        # ✅ Используем рабочую модель на Replicate
        headers = {
            "Authorization": f"Token {REPLICATE_API_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "version": "ac732df83ceee82476b85ae97e7fd2477b928505428898884354238172485242",  # stability-ai/stable-diffusion
            "input": {
                "image": file_url,
                "prompt": f"{style_key} style, masterpiece, best quality",
                "num_inference_steps": 20
            }
        }

        response = requests.post("https://api.replicate.com/v1/predictions", headers=headers, json=payload)

        if response.status_code != 201:
            await bot.send_message(user_id, f"❌ Ошибка API: {response.status_code}, {response.text}")
            logging.error(f"Replicate API error: {response.status_code} - {response.text}")
            return

        result = response.json()
        prediction_id = result["id"]

        # Ждём завершения обработки
        while True:
            time.sleep(2)
            status_response = requests.get(f"https://api.replicate.com/v1/predictions/{prediction_id}", headers=headers)
            status_result = status_response.json()

            if status_result["status"] == "succeeded":
                output_url = status_result["output"][0]
                await bot.send_photo(user_id, photo=output_url, caption="✨ Вот твой арт!")
                break
            elif status_result["status"] == "failed":
                await bot.send_message(user_id, "❌ Не удалось обработать. Попробуй другое фото.")
                break

    except Exception as e:
        await bot.send_message(user_id, "Ошибка при генерации. Попробуй позже.")
        logging.error(f"Exception in process_image: {e}")

# Команды
@dp.message(Command("start"))
async def start(message: Message):
    styles_list = ", ".join(STYLES.keys())
    await bot.send_message(
        message.from_user.id,
        "🎨 Привет! Я — бот-художник.\n"
        f"Стили: {styles_list}\n\n"
        "1. Напиши название стиля\n"
        "2. Отправь фото\n\n"
        "Бот бесплатный, без ограничений!"
    )

# Обработка текста (выбор стиля)
@dp.message(lambda msg: msg.text and not msg.photo)
async def handle_text(message: Message):
    text = message.text.strip().lower()
    for name, key in STYLES.items():
        if text == name.lower():
            user_style[message.from_user.id] = key
            await bot.send_message(message.from_user.id, f"Отлично! Теперь пришли фото для стиля «{name}».")
            return
    await bot.send_message(message.from_user.id, "Неизвестный стиль. Доступные: " + ", ".join(STYLES.keys()))

# Обработка фото
@dp.message(lambda msg: msg.photo)
async def handle_photo(message: Message):
    await process_image(message)

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
    await bot.session.close()

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
