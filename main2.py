# main2.py
# Бесплатный Telegram-бот для стилизации изображений с Pillow
# Поддерживает стиль "графический" через набор фильтров Pillow
# Функционал: /start, /styles (инлайн-кнопки), /style <название> (ручной выбор),
# отправка изображения -> бот возвращает изображение с примененным стилем.

import os
import json
import logging
import tempfile
import io

from PIL import Image, ImageOps, ImageFilter

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Глобальный список стилей
STYLES = [
    "grayscale",
    "sepia",
    "negative",
    "blur",
    "sharpen",
    "edge_enhance",
    "contour",
    "emboss",
    "posterize",
]

STATE_FILE = "state.json"
state = {}  # структура: { "chat_id_str": "style" }

def load_state():
    global state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as e:
            logger.error("Не удалось загрузить состояние: %s", e)
            state = {}

def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Не удалось сохранить состояние: %s", e)

def apply_style(img: Image.Image, style: str) -> Image.Image:
    """Применяет выбранный стиль к изображению (Pillow)."""
    img = img.convert("RGB")
    if style == "grayscale":
        return ImageOps.grayscale(img).convert("RGB")
    if style == "sepia":
        gray = ImageOps.grayscale(img)
        sepia = ImageOps.colorize(gray, "#704214", "#C0A080")
        return sepia
    if style == "negative":
        return ImageOps.invert(img)
    if style == "blur":
        return img.filter(ImageFilter.GaussianBlur(radius=2))
    if style == "sharpen":
        return img.filter(ImageFilter.SHARPEN)
    if style == "edge_enhance":
        return img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    if style == "contour":
        return img.filter(ImageFilter.CONTOUR)
    if style == "emboss":
        return img.filter(ImageFilter.EMBOSS)
    if style == "posterize":
        return ImageOps.posterize(img, 4)
    # Если стиль не найден — вернуть оригинал без изменений
    return img

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    load_state()
    current = state.get(str(chat_id), None)
    msg = (
        f"Привет, {user.first_name}! Я могу стилизовать ваше изображение.\n"
        f"Доступные стили: {', '.join(STYLES)}\n"
        f"Текущий стиль: {current if current else 'не установлен'}\n\n"
        "Используйте /styles чтобы выбрать стиль, или отправьте /style <название> например: /style sepia\n"
        "Затем отправьте изображение."
    )
    await update.message.reply_text(msg)

async def show_styles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Создаём кнопки стилями (инлайн-клавиатура)
    rows = []
    row = []
    for i, s in enumerate(STYLES, 1):
        row.append(InlineKeyboardButton(s, callback_data=s))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:  # остаток кнопок
        rows.append(row)
    keyboard = InlineKeyboardMarkup(rows)
    await update.message.reply_text("Выберите стиль обработки:", reply_markup=keyboard)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    style = query.data
    chat_id = query.message.chat.id
    state[str(chat_id)] = style
    save_state()
    await query.edit_message_text(text=f"Стиль установлен: {style}. Пришли изображение, и я применю стиль.")

async def set_style_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text(
            "Использование: /style <название_стиля>\nДоступные стили: " + ", ".join(STYLES)
        )
        return
    style = context.args[0]
    if style not in STYLES:
        await update.message.reply_text(
            "Неправильный стиль. Доступные стили: " + ", ".join(STYLES)
        )
        return
    chat_id = update.effective_chat.id
    state[str(chat_id)] = style
    save_state()
    await update.message.reply_text(f"Стиль установлен: {style}. Пришлите изображение.")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Определяем стиль для этого чата
    load_state()
    chat_id = update.effective_chat.id
    style = state.get(str(chat_id), "grayscale")

    # Получаем файл изображения (можно как фото, так и документ с изображением)
    file = None
    file_name_hint = "image.jpg"

    if update.message.photo:
        # Фото с наибольшим разрешением
        photo = update.message.photo[-1]
        file = await photo.get_file()
        file_name_hint = f"photo_{photo.file_id}.jpg"
    elif update.message.document:
        # Документ — проверить mime-type
        mime = update.message.document.mime_type or ""
        if mime.startswith("image/"):
            file = await update.message.document.get_file()
            file_name_hint = update.message.document.file_name or "image.jpg"
        else:
            await update.message.reply_text("Принимаю только изображения (image/*). Попробуйте другое сообщение.")
            return
    else:
        await update.message.reply_text("Пожалуйста, отправьте изображение (фото или документ-изображение).")
        return

    # Скачиваем файл во временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        await file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    try:
        img = Image.open(tmp_path).convert("RGB")
        processed = apply_style(img, style)

        buf = io.BytesIO()
        processed.save(buf, format="JPEG")
        buf.seek(0)

        await update.message.reply_photo(photo=buf, caption=f"Стиль: {style}")
    except Exception as e:
        logger.exception("Ошибка обработки изображения: %s", e)
        await update.message.reply_text("Произошла ошибка при обработке изображения.")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass  # игнорируем ошибки удаления

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Укажите TELEGRAM_BOT_TOKEN как переменную окружения.")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("styles", show_styles))
    app.add_handler(CommandHandler("style", set_style_command))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_image))

    logger.info("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()

