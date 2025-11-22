import os
import logging
import wikipedia
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Устанавливаем язык Википедии — русский
wikipedia.set_lang("ru")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напишите любое слово или запрос, и я постараюсь найти статью на русской Википедии."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Пожалуйста, введите непустой запрос.")
        return

    try:
        # Поиск статьи (берём первую по релевантности)
        page = wikipedia.page(query, auto_suggest=True)
        summary = wikipedia.summary(query, sentences=5)
        link = page.url
        response = f"{summary}\n\nПодробнее: {link}"
        await update.message.reply_text(response, disable_web_page_preview=False)
    except wikipedia.exceptions.DisambiguationError as e:
        options = ', '.join(e.options[:5])  # первые 5 вариантов
        await update.message.reply_text(
            f"Запрос неоднозначен. Возможно, вы имели в виду: {options}?"
        )
    except wikipedia.exceptions.PageError:
        await update.message.reply_text("Статья по вашему запросу не найдена.")
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса '{query}': {e}")
        await update.message.reply_text("Произошла ошибка при поиске. Попробуйте другой запрос.")

def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("Не задана переменная окружения BOT_TOKEN")
    
    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
