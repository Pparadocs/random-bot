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

# Вспомогательные функции
async def generate_image(message: Message):
    user_id = message.from_user.id
    prompt = message.text.strip()
    if not prompt:
        await bot.send_message(user_id, "Напиши, что хочешь сгенерировать.")
        return

    await bot.send_message(user_id, "⏳ Генерирую... (5–10 сек)")

    try:
        # ✅ Используем рабочую модель: stability-ai/sdxl
        headers = {
            "Authorization": f"Token {REPLICATE_API_TOKEN}",
            "Content-Type": "application/json"
        }

        # ✅ Новый version
        version = "7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc"

        payload = {
            "version": version,
            "input": {
                "prompt": f"{prompt}, masterpiece, best quality",
                "num_inference_steps": 20
            }
        }

        response = requests.post("https://api.replicate.com/v1/predictions", headers=headers, json=payload)

        if response.status_code != 201:
            # ✅ Безопасный парсинг ошибки
            try:
                error_data = response.json()
                error = error_data.get("detail", f"Ошибка API: {response.status_code}")
            except Exception:
                error = f"Ошибка API: {response.status_code}, {response.text[:200]}"
            await bot.send_message(user_id, f"❌ {error}")
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
                if not output_url:
                    await bot.send_message(user_id, "❌ Не удалось получить результат. Попробуй снова.")
                    return
                await bot.send_photo(user_id, photo=output_url, caption=f"✨ Вот твой арт:\n<i>{prompt}</i>", parse_mode="HTML")
                break
            elif status_result["status"] == "failed":
                await bot.send_message(user_id, "❌ Не удалось сгенерировать. Попробуй другой запрос.")
                break

    except Exception as e:
        await bot.send_message(user_id, "Ошибка при генерации. Попробуй позже.")
        logging.error(f"Exception in generate_image: {e}")

# Команды
@dp.message(Command("start"))
async def start(message: Message):
    await bot.send_message(
        message.from_user.id,
        "🎨 Привет! Напиши, что хочешь сгенерировать — и я создам изображение.\n\n"
        "Например: «кот в космосе», «аниме девушка с мечом»."
    )

# Обработка текста (генерация по промту)
@dp.message(lambda msg: msg.text and not msg.photo)
async def handle_text(message: Message):
    await generate_image(message)

# Обработка фото (игнорируем)
@dp.message(lambda msg: msg.photo)
async def handle_photo(message: Message):
    await bot.send_message(message.from_user.id, "Я генерирую изображения по тексту. Напиши, что хочешь увидеть.")

# aiohttp routes
async def handle_webhook(request: web.Request):
    try:
        json_string = await request.text()  # ✅ Получаем тело как строку
        update = Update.model_validate_json(json_string)  # ✅ Парсим строку как JSON
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
