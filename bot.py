import os
import logging
import json
import csv
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
)
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes 
from PIL import Image

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

# Загрузка токена и текстов
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен Telegram бота не найден! Убедитесь, что переменная TELEGRAM_BOT_TOKEN указана в .env.")

with open("messages.json", "r", encoding="utf-8") as f:
    BOT_TEXTS = json.load(f)

with open("keyboard_texts.json", "r", encoding="utf-8") as f:
    KEYBOARD_TEXTS = json.load(f)

# Глобальное хранилище данных
user_data = {}

# Вспомогательные функции
def create_image(layers):
    """Создает итоговое изображение, накладывая слои."""
    if not layers:
        return None
    base = Image.open(layers[0]).convert("RGBA")
    for layer_path in layers[1:]:
        layer = Image.open(layer_path).convert("RGBA")
        base.paste(layer, (0, 0), layer)
    return base

def save_to_csv(user_id):
    """Сохраняет данные пользователя в CSV."""
    file_exists = os.path.isfile("contestants.csv")
    with open("contestants.csv", "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["User ID", "Choices"])
        writer.writerow([user_id, ", ".join(user_data[user_id]["choices"])])
    logger.info(f"Данные пользователя {user_id} записаны в CSV.")

# Бот: Шаги
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствует пользователя и предлагает начать процесс."""
    user_id = update.effective_user.id
    user_data[user_id] = {"step": 0, "choices": [], "layers": []}
    logger.info(f"Пользователь {user_id} запустил бота.")

    keyboard = [[KeyboardButton("Продолжить")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(BOT_TEXTS["greeting"], reply_markup=reply_markup)

async def continue_to_step_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переход к первому шагу."""
    await step_1(update, context)

async def step_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 1: Выбор фона."""
    user_id = update.effective_user.id
    step_folder = "assets/1 ШАГ"
    images = sorted([img for img in os.listdir(step_folder) if img.lower().endswith((".jpg", ".jpeg", ".png"))])

    # Инлайн-клавиатура
    keyboard_texts = sorted(KEYBOARD_TEXTS["step_1_buttons"]) 
    keyboard = [
        [InlineKeyboardButton(keyboard_texts[i], callback_data=f"step_1_{i}")]
        for i in range(len(images))
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(BOT_TEXTS["step_1_prompt"], reply_markup=reply_markup)

async def handle_step_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор фона."""
    query = update.callback_query
    user_id = query.from_user.id
    step_folder = "assets/1 ШАГ"
    images = sorted([img for img in os.listdir(step_folder) if img.lower().endswith((".jpg", ".jpeg", ".png"))])

    # Получаем выбор пользователя
    choice_index = int(query.data.split("_")[-1])
    chosen_image = images[choice_index]
    user_data[user_id]["choices"].append(chosen_image)
    user_data[user_id]["layers"].append(os.path.join(step_folder, chosen_image))
    await context.bot.send_photo(chat_id=user_id, photo=open(os.path.join(chosen_image)

    logger.info(f"Пользователь {user_id} выбрал фон: {chosen_image}.")
    await step_2(update, context)

async def step_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 2: Выбор вариации фона."""
    query = update.callback_query
    user_id = query.message.chat_id
    previous_choice = os.path.splitext(user_data[user_id]["choices"][-1])[0]
    step_folder = f"assets/2 ШАГ/{previous_choice}"
    #images = sorted(os.listdir(step_folder))
    images = sorted([img for img in os.listdir(step_folder) if img.lower().endswith((".jpg", ".jpeg", ".png"))])
    logger.info(images, step_folder)
    # Отправляем фотографии
    media_group = [
        InputMediaPhoto(media=open(os.path.join(step_folder, img), "rb"))
        for img in images
    ]
    await context.bot.send_media_group(chat_id=user_id, media=media_group)

    # Инлайн-клавиатура
    keyboard_texts = sorted(KEYBOARD_TEXTS["step_2_buttons"])
    keyboard = [
        [InlineKeyboardButton(keyboard_texts[i], callback_data=f"step_2_{i}")]
        for i in range(len(images))
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
    chat_id=query.message.chat_id,
    text=BOT_TEXTS["step_2_prompt"],
    reply_markup=reply_markup
    )

async def handle_step_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор вариации фона."""
    query = update.callback_query
    user_id = query.from_user.id
    previous_choice = [os.path.splitext(choice)[0] for
                       choice in  user_data[user_id]["choices"]]
    base_choice = previous_choice[0]
    step_folder = f"assets/2 ШАГ/{base_choice}"
    #images = sorted(os.listdir(step_folder))
    images = sorted([img for img in os.listdir(step_folder) if img.lower().endswith((".jpg", ".jpeg", ".png"))])

    # Получаем выбор пользователя
    choice_index = int(query.data.split("_")[-1])
    chosen_image = images[choice_index]
    user_data[user_id]["choices"].append(chosen_image)
    user_data[user_id]["layers"].append(os.path.join(step_folder, chosen_image))

    logger.info(f"Пользователь {user_id} выбрал вариацию: {chosen_image}.")
    await query.answer("Вариация выбрана.")
    await step_3(update, context)

async def step_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 3: Выбор атрибута."""
    query = update.callback_query
    user_id = query.from_user.id
    previous_choice = [os.path.splitext(choice)[0] for
                       choice in  user_data[user_id]["choices"]]
    logger.info(user_data[user_id])
    base_choice, season = previous_choice
    step_folder = f"assets/3 ШАГ/{base_choice}/{season}"
    images = sorted([img for img in os.listdir(step_folder) if img.lower().endswith((".jpg", ".jpeg", ".png"))])

    # Отправляем фотографии
    media_group = [
        InputMediaPhoto(media=open(os.path.join(step_folder, img), "rb"))
        for i, img in enumerate(images)
    ]
    await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)

    # Инлайн-клавиатура
    keyboard_texts = sorted(KEYBOARD_TEXTS["step_3_buttons"])
    keyboard = [
        [InlineKeyboardButton(keyboard_texts[i], callback_data=f"step_3_{i}")]
        for i in range(len(images))
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
    chat_id=query.message.chat_id,
    text=BOT_TEXTS["step_3_prompt"],
    reply_markup=reply_markup
    )

async def handle_step_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор атрибута."""
    query = update.callback_query
    user_id = query.from_user.id
    previous_choice = [os.path.splitext(choice)[0] for
                       choice in  user_data[user_id]["choices"]]
    base_choice, season = previous_choice.split()
    step_folder = f"assets/3 ШАГ/{base_choice}/{season}"
    images = sorted(os.listdir(step_folder))

    # Получаем выбор пользователя
    choice_index = int(query.data.split("_")[-1])
    chosen_image = images[choice_index]
    user_data[user_id]["choices"].append(chosen_image)
    user_data[user_id]["layers"].append(os.path.join(step_folder, chosen_image))

    logger.info(f"Пользователь {user_id} выбрал атрибут: {chosen_image}.")
    await query.answer("Атрибут выбран.")
    await step_4(update, context)

async def step_4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 4: Выбор подписи."""
    query = update.callback_query
    user_id = query.from_user.id
    step_folder = "assets/4 ШАГ"
    images = sorted([img for img in os.listdir(step_folder) if img.lower().endswith((".jpg", ".jpeg", ".png"))])

    # Отправляем фотографии
    media_group = [
        InputMediaPhoto(media=open(os.path.join(step_folder, img), "rb"))
        for img in images
    ]
    await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)

    # Инлайн-клавиатура
    keyboard = [
        [InlineKeyboardButton(KEYBOARD_TEXTS["step_4_buttons"][i], callback_data=f"step_4_{i}")]
        for i in range(len(images))
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
    chat_id=query.message.chat_id,
    text=BOT_TEXTS["step_4_prompt"],
    reply_markup=reply_markup
    )

async def handle_step_4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор подписи."""
    query = update.callback_query
    user_id = query.from_user.id
    step_folder = "assets/4 ШАГ"
    images = sorted([img for img in os.listdir(step_folder) if img.lower().endswith((".jpg", ".jpeg", ".png"))])

    # Получаем выбор пользователя
    choice_index = int(query.data.split("_")[-1])
    chosen_image = images[choice_index]
    user_data[user_id]["choices"].append(chosen_image)
    user_data[user_id]["layers"].append(os.path.join(step_folder, chosen_image))

    logger.info(f"Пользователь {user_id} выбрал подпись: {chosen_image}.")
    await query.answer("Подпись выбрана.")
    await step_5(query, context)

# Реализуйте аналогично шаги 3, 4 и 5. После шага 5 предложите "Поделиться".

async def share_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает итоговое изображение и предлагает поделиться."""
    user_id = update.from_user.id
    final_image = create_image(user_data[user_id]["layers"])
    final_path = f"final_images/{user_id}_final.png"
    final_image.save(final_path)

    keyboard = [[InlineKeyboardButton("Поделиться", switch_inline_query="Поделитесь открыткой!")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_photo(photo=open(final_path, "rb"))
    await update.message.reply_text(BOT_TEXTS["share_prompt"], reply_markup=reply_markup)
    save_to_csv(user_id)
    await update.message.reply_text(BOT_TEXTS["contest_message"])

# Основная функция
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Продолжить$"), continue_to_step_1))
    app.add_handler(CallbackQueryHandler(handle_step_1, pattern="^step_1_"))
    app.add_handler(CallbackQueryHandler(handle_step_2, pattern="^step_2_"))
    app.add_handler(CallbackQueryHandler(handle_step_3, pattern="^step_3_"))
    # Зарегистрируйте обработчики для шагов 3, 4, 5 и кнопки "Поделиться"
    app.run_polling()

