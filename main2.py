import os
import time
import re
import logging
import requests
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.types import Message
from aiogram.filters import Command
from aiohttp import web

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
QR_FILE_ID = os.getenv("QR_FILE_ID")

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Стили
STYLES = {
    "конфетти": "candy",
    "мозаика": "mosaic",
    "принцесса дождя": "rain_princess",
    "удни": "udnie"
}

# Хранилища
user_style = {}                # {user_id: style_key}
paid_users = {}                # {user_id: timestamp_окончания}
user_usage_count = {}          # {user_id: count}
pending_payments = {}          # {user_id: file_id_скрина}

# Вспомогательные функции
def is_paid(user_id: int) -> bool:
    if user_id in paid_users:
        if time.time() < paid_users[user_id]:
            return True
        else:
            del paid_users[user_id]
    return False

def can_use_free(user_id: int) -> bool:
    return user_usage_count.get(user_id, 0) < 2

def increment_usage(user_id: int):
    user_usage_count[user_id] = user_usage_count.get(user_id, 0) + 1

def grant_access(user_id: int, hours: int = 24):
    paid_users[user_id] = time.time() + hours * 3600

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
        import requests
        # ✅ Исправленный URL для Hugging Face Inference API
        API_URL = f"https://router.huggingface.co/hf-inference/models/akhooli/fast-style-transfer/{style_key}"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        response = requests.post(API_URL, headers=headers, json={"inputs": file_url}, timeout=60)

        if response.status_code == 200:
            # ✅ Отправляем фото напрямую из байтов
            await bot.send_photo(user_id, photo=response.content, caption="✨ Вот твой арт!")
        elif response.status_code == 503:
            # Сервис занят — попробуй позже
            await bot.send_message(user_id, "🔧 Модель загружается... Попробуй через 1-2 минуты.")
        else:
            # ✅ Безопасный парсинг ошибки
            try:
                error_data = response.json()
                error = error_data.get("error", "Неизвестная ошибка API")
            except Exception:
                error = f"Ошибка API: {response.status_code}, {response.text[:200]}"
            await bot.send_message(user_id, f"❌ Ошибка обработки: {error}")
            logging.error(f"HF API error: {response.status_code} - {response.text}")

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
        "У тебя **2 бесплатных использования** — потом /pay"
    )

@dp.message(Command("pay"))
async def cmd_pay(message: Message):
    # ✅ Временно убрана отправка QR-кода, чтобы избежать ошибки `wrong file identifier`
    await bot.send_message(
        message.from_user.id,
        "🎨 Поддержи бота — 99 ₽ за 24 часа неограниченного доступа!\n\n"
        "✅ Как оплатить:\n"
        "1. Открой СБП в своём приложении (Сбер, ВТБ, Тинькофф и т.д.).\n"
        "2. Введи сумму: **99 ₽**\n"
        "3. Комментарий: *«Бот-артист»*\n"
        "4. Подтверди перевод.\n\n"
        "После оплаты пришли скриншот подтверждения — и получишь доступ!"
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
    user_id = message.from_user.id

    if is_paid(user_id):
        await process_image(message)
        return

    if can_use_free(user_id):
        increment_usage(user_id)
        await process_image(message)
        remaining = 2 - user_usage_count[user_id]
        if remaining > 0:
            await bot.send_message(user_id, f"🎨 Осталось бесплатных использований: {remaining}")
        else:
            await bot.send_message(
                user_id,
                "🎨 Твои **2 бесплатных использования** закончились!\n"
                "Хочешь больше? Поддержи бота — 99 ₽ за 24 часа неограниченного доступа!\n"
                f"🔗 /pay"
            )
        return

    # Если лимит превышен
    await bot.send_message(
        user_id,
        "🎨 Лимит бесплатных использований исчерпан.\n"
        "Поддержи бота — 99 ₽ за 24 часа неограниченного доступа!\n"
        f"🔗 /pay"
    )

# Приём скриншотов оплаты
@dp.message(lambda msg: msg.photo and user_usage_count.get(msg.from_user.id, 0) >= 2 and not is_paid(msg.from_user.id))
async def handle_payment_proof(message: Message):
    user_id = message.from_user.id
    pending_payments[user_id] = message.photo[-1].file_id
    await bot.send_message(user_id, "✅ Скриншот получен! Ожидай подтверждения (обычно в течение часа).")

    if ADMIN_ID:
        try:
            await bot.send_photo(
                ADMIN_ID,
                photo=message.photo[-1].file_id,
                caption=f"📥 Новый платёж!\nID: {user_id}\nUsername: @{message.from_user.username or 'нет'}\n\n"
                        f"Чтобы подтвердить, отправь: /approve_{user_id}"
            )
        except Exception as e:
            logging.error(f"Не удалось отправить админу: {e}")

# Подтверждение от админа
@dp.message(lambda msg: str(msg.from_user.id) == str(ADMIN_ID) and msg.text)
async def admin_approve(message: Message):
    text = message.text.strip()
    match = re.match(r"/approve_(\d+)", text)
    if match:
        user_id = int(match.group(1))
        grant_access(user_id, hours=24)
        try:
            await bot.send_message(user_id, "✅ Оплата подтверждена! У тебя 24 часа неограниченного доступа. Твори!")
        except:
            pass
        await bot.send_message(ADMIN_ID, f"✅ Доступ выдан пользователю {user_id}")
        return

    await bot.send_message(ADMIN_ID, "Неизвестная команда. Используй: /approve_123456789")

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
