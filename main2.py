import os
import sys
import logging
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import wikipedia

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Проверка TELEGRAM_TOKEN
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logging.error("❌ Переменная окружения TELEGRAM_TOKEN не задана!")
    sys.exit(1)

# Получаем RENDER_URL для webhook
RENDER_URL = os.environ.get("RENDER_URL", "").rstrip("/")
if not RENDER_URL:
    logging.warning("⚠️ RENDER_URL не задан — webhook не будет установлен.")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = RENDER_URL + WEBHOOK_PATH if RENDER_URL else ""

# Инициализация Flask и Telegram Application (без Updater)
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
application = Application.builder().token(TELEGRAM_TOKEN).updater(None).build()

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напишите слово — я найду статью в русской Википедии."
    )

async def search_wikipedia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Пожалуйста, введите непустой запрос.")
        return

    try:
        wikipedia.set_lang("ru")
        summary = wikipedia.summary(query, sentences=3)
        page = wikipedia.page(query)
        response = f"{summary}\n\n📖 Читать: {page.url}"
    except wikipedia.exceptions.DisambiguationError as e:
        options = "\n".join(e.options[:5])
        response = f"Неоднозначный запрос. Варианты:\n{options}"
    except wikipedia.exceptions.PageError:
        response = "Статья не найдена. Попробуйте другой запрос."
    except Exception as e:
        logging.error(f"Ошибка при поиске '{query}': {e}")
        response = "Произошла ошибка. Попробуйте позже."

    await update.message.reply_text(response)

# Регистрация обработчиков
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_wikipedia))

# Flask route для webhook
@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    # Явно указываем, что ожидаем JSON
    if request.content_type != 'application/json':
        logging.warning(f"❌ Неожиданный Content-Type: {request.content_type}")
        return jsonify({"error": "Content-Type must be application/json"}), 400

    json_data = request.get_json(silent=True)
    if not json_data:
        logging.warning("❌ Не удалось распарсить JSON из тела запроса")
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        update = Update.de_json(json_data, bot)
        application.update_queue.put_nowait(update)
        return jsonify({"status": "ok"})
    except Exception as e:
        logging.error(f"❌ Ошибка при обработке обновления: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def home():
    return "✅ Wikipedia Bot is running on Render!"

# Установка webhook при старте
def set_webhook():
    if WEBHOOK_URL:
        logging.info(f"ℹ️ Webhook должен быть установлен на: {WEBHOOK_URL}")
        logging.info("ℹ️ Установите webhook вручную через API Telegram.")
    else:
        logging.warning("⚠️ RENDER_URL не задан — webhook не установлен")

# Запуск
if __name__ == "__main__":
    set_webhook()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
