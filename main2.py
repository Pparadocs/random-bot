import os
import sys
import requests
import logging
from flask import Flask, request, jsonify
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

# Flask-приложение
app = Flask(__name__)

# --- Функции для взаимодействия с Telegram API ---
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'  # Опционально, для форматирования
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"❌ Ошибка при отправке сообщения: {e}")
        return False

def setup_webhook():
    if WEBHOOK_URL:
        set_webhook_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}"
        try:
            response = requests.get(set_webhook_url, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}")
                else:
                    logging.error(f"❌ Ошибка API при установке webhook: {result}")
            else:
                logging.error(f"❌ Ошибка HTTP при установке webhook: {response.status_code}")
        except Exception as e:
            logging.error(f"❌ Исключение при установке webhook: {e}")
    else:
        logging.warning("⚠️ RENDER_URL не задан — webhook не установлен")

# --- Flask routes ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "no data"}), 400

        if 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            text = message.get('text', '').strip()
            user_id = message['from']['id']

            logging.info(f"Получено сообщение: '{text}' от {user_id}")

            if text == '/start':
                reply = "Привет! Напишите слово — я найду статью в русской Википедии."
                send_message(chat_id, reply)
                return jsonify({'status': 'ok'})

            # Обработка текста (поиск в Википедии)
            if text:
                try:
                    wikipedia.set_lang("ru")
                    summary = wikipedia.summary(text, sentences=3)
                    page = wikipedia.page(text)
                    reply = f"{summary}\n\n📖 Читать: [{page.title}]({page.url})"
                except wikipedia.exceptions.DisambiguationError as e:
                    options = "\n".join(e.options[:5])
                    reply = f"Неоднозначный запрос. Варианты:\n{options}"
                except wikipedia.exceptions.PageError:
                    reply = "Статья не найдена. Попробуйте другой запрос."
                except Exception as e:
                    logging.error(f"Ошибка при поиске '{text}': {e}")
                    reply = "Произошла ошибка при поиске. Попробуйте позже."

                send_message(chat_id, reply)
                return jsonify({'status': 'ok'})

        # Если не message, игнорируем (например, callback_query, edited_message и т.д.)
        return jsonify({'status': 'ok'})

    except Exception as e:
        logging.error(f"Ошибка в webhook_handler: {e}")
        return jsonify({'status': 'error'}), 500

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def home():
    return "✅ Wikipedia Bot is running on Render!"

# Установка webhook при запуске (важно для Render)
if __name__ != '__gunicorn__':
    setup_webhook()
    logging.info("Webhook должен быть установлен при запуске.")
else:
    # При запуске через gunicorn, вызываем setup_webhook() вручную или через env.
    setup_webhook()
    logging.info("Webhook установлен через gunicorn.")

# Запуск (для локального тестирования)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
