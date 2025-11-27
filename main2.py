import os
import logging
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import wikipedia

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получаем токен и URL сервиса из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL", "")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = RENDER_URL + WEBHOOK_PATH if RENDER_URL else ""

app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напишите мне слово или запрос, и я пришлю статью из Википедии."
    )

# Обработчик текстовых сообщений
async def search_wikipedia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    try:
        wikipedia.set_lang("ru")  # Используем русскую Википедию
        page = wikipedia.page(query)
        summary = wikipedia.summary(query, sentences=3)
        response = f"{summary}\n\nЧитать полностью: {page.url}"
    except wikipedia.exceptions.DisambiguationError as e:
        response = "Запрос неоднозначен. Попробуйте уточнить, например:\n" + "\n".join(e.options[:5])
    except wikipedia.exceptions.PageError:
        response = "Статья не найдена. Попробуйте другой запрос."
    except Exception as e:
        response = "Произошла ошибка при поиске. Попробуйте позже."
        logging.error(f"Ошибка при поиске '{query}': {e}")

    await update.message.reply_text(response)

# Регистрация обработчиков
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_wikipedia))

# Flask route для webhook
@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    if request.method == "POST":
        json_data = request.get_json()
        update = Update.de_json(json_data, bot)
        application.update_queue.put_nowait(update)
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 400

@app.route("/health")
def health():
    return "OK"

@app.route("/")
def home():
    return "Wikipedia Bot is running!"

# Установка webhook при запуске
def set_webhook():
    if WEBHOOK_URL:
        bot.set_webhook(url=WEBHOOK_URL)
        logging.info(f"Webhook установлен: {WEBHOOK_URL}")
    else:
        logging.warning("RENDER_URL не задан — webhook не установлен")

if __name__ == "__main__":
    set_webhook()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
