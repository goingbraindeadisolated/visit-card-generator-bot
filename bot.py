import os
import logging
import json
import csv
from io import BytesIO
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
)
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes 
from PIL import Image


load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен Telegram бота не найден! Убедитесь, что переменная TELEGRAM_BOT_TOKEN указана в .env.")

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Путь к папкам на каждом шаге
STEP_FOLDERS = {
    1: "assets/1 ШАГ",
    2: "assets/2 ШАГ",
    3: "assets/3 ШАГ",
    4: "assets/4 шаг",
    5: "assets/5 шаг"
}

with open("messages.json", "r", encoding="utf-8") as f:
    BOT_TEXTS = json.load(f)

with open("keyboard_texts.json", "r", encoding="utf-8") as f:
    KEYBOARD_TEXTS = json.load(f)

def create_final_image(layers):
    if not layers:
        raise ValueError("Слои не найдены!")
    
    # Открываем первый слой как базовое изображение
    base = Image.open(layers[0]).convert("RGBA")
    
    # Накладываем все остальные слои
    for layer_path in layers[1:]:
        layer = Image.open(layer_path).convert("RGBA")
        base.paste(layer, (0, 0), layer)
    
    return base

async def greetings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствует пользователя и предлагает начать процесс."""
    user_id = update.effective_user.id
    context.user_data['current_img'] = BytesIO()
    context.user_data['step'] = 1
    logger.info(f"Пользователь {user_id} запустил бота.")

    keyboard = [[KeyboardButton(KEYBOARD_TEXTS['greeting'])]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(BOT_TEXTS["greeting"], reply_markup=reply_markup)

# Универсальная функция для отправки вариантов
async def send_step_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет пользователю варианты для текущего шага."""
    user_id = update.effective_user.id if update.effective_user.id else update.callback.query.from_user.id
    chat_id = update.callback_query.message.chat_id if update.callback_query else update.message.chat_id

    # Определяем текущий шаг
    step = context.user_data.get("step", 1)
    step_folder = STEP_FOLDERS[step]
    
    # Список изображений в папке
    images = sorted([
        img for img in os.listdir(step_folder)
        if img.lower().endswith((".jpg", ".jpeg", ".png"))
    ])
    
    # Создаём инлайн-клавиатуру
    keyboard_texts = sorted(KEYBOARD_TEXTS[str(step)])
    keyboard = [
        [InlineKeyboardButton(text, callback_data=f"choice_{i}")]
        for i, text in enumerate(keyboard_texts)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с вариантами
    await context.bot.send_message(
        chat_id=chat_id,
        text=BOT_TEXTS[str(step)],
        reply_markup=reply_markup
    )

# Основной обработчик для всех шагов
async def handle_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Универсальный обработчик выбора пользователя."""
    user_id = update.effective_user.id if update.effective_user.id else update.callback.query.from_user.id
    chat_id = update.callback_query.message.chat_id if update.callback_query else update.message.chat_id

    # Текущий шаг
    step = context.user_data.get("step", 1)
    step_folder = STEP_FOLDERS[step]

    # Получаем выбор пользователя
    choice_index = int(update.callback_query.data.split("_")[-1])
    images = sorted([
        img for img in os.listdir(step_folder)
        if img.lower().endswith((".jpg", ".jpeg", ".png"))
    ])
    chosen_image_path = os.path.join(step_folder, images[choice_index])

    # Если шаг 4 или 5, создаём итоговое изображение
    if step in [4, 5]:
        layers = context.user_data.get("layers", [])
        final_image = create_final_image(layers, chosen_image_path)

        # Сохраняем итоговое изображение как временный файл
        temp_path = f"temp_images/{user_id}_step_{step}.png"
        os.makedirs("temp_images", exist_ok=True)
        final_image.save(temp_path, format="PNG")

        # Обновляем слои в user_data
        context.user_data["layers"] = layers + [temp_path]

        # Отправляем изображение пользователю
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=open(temp_path, "rb")
        )
    else:
        # Для шагов 1-3 сохраняем путь к выбранному слою
        context.user_data.setdefault("layers", []).append(chosen_image_path)

        # Отправляем выбранное изображение
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=open(chosen_image_path, "rb"),
            caption=f"Вы выбрали: {os.path.basename(chosen_image_path)}"
        )

    # Увеличиваем шаг
    if step < 5:
        context.user_data["step"] = step + 1
        await send_step_options(update, context)
    else:
        await query.answer("Создание завершено!")
        await show_final_result(update, context)

# Финальная функция для показа результата
async def show_final_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает итоговое изображение и предлагает поделиться."""
    user_id = update.callback_query.from_user.id
    chat_id = update.callback_query.message.chat_id

    # Итоговое изображение
    final_image_path = context.user_data["layers"][-1]
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=open(final_image_path, "rb"),
        caption="Ваше итоговое изображение готово!"
    )

    # Кнопка "Поделиться"
    keyboard = [[InlineKeyboardButton("Поделиться", switch_inline_query="Посмотрите мою открытку!")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text="Поделитесь результатом с друзьями!",
        reply_markup=reply_markup
    )

# Основная функция
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", greetings))
    app.add_handler(MessageHandler(filters.TEXT
                                   & filters.Regex("^Сделать открытку$"),
                                   send_step_options))
    app.add_handler(CallbackQueryHandler(handle_step, pattern="^choice_"))
    app.run_polling()

