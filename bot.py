import os
import logging
import json
import csv
from dotenv import load_dotenv
from io import BytesIO
from telegram import InlineQueryResultPhoto
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, InlineQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters
)
from PIL import Image

# Подключение переменных окружения
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

# Загрузка текстов из JSON
with open("bot_texts.json", "r", encoding="utf-8") as f:
    BOT_TEXTS = json.load(f)
with open("keyboard_texts.json", "r", encoding="utf-8") as f:
    KEYBOARD_TEXTS = json.load(f)

# Формирование пути к папке
def compose_path(step, previous_choices):
    """Формирует путь к папке на основе текущего шага и предыдущих выборов."""
    base_path = f"assets/{step} ШАГ" if step < 3 else f"assets/{step-1} ШАГ"
    if step == 1:
        return base_path
    elif step == 2:
        return os.path.join(base_path, previous_choices[0])
    elif step == 4:
        return os.path.join(base_path, previous_choices[0], previous_choices[1])
    elif step in [5, 6]:
        return f"assets/{step-1} шаг"
    return base_path

# Создание итогового изображения
def create_final_image(base_image_path, overlay_image_path):
    """Создаёт изображение, накладывая один слой на другой."""
    base_image = Image.open(base_image_path).convert("RGBA")
    overlay = Image.open(overlay_image_path).convert("RGBA")
    base_image.paste(overlay, (0, 0), overlay)
    return base_image

# Функция для команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие пользователя с кнопкой 'Продолжить'."""
    user_id = update.effective_user.id
    context.user_data.clear()  # Очищаем user_data для нового пользователя
    context.user_data["step"] = 1  # Устанавливаем начальный шаг
    context.user_data["choices"] = []  # Инициализируем список выборов
    logger.info(f"Пользователь {user_id} начал взаимодействие с ботом.")

    # Создаём обычную клавиатуру с кнопкой "Продолжить"
    keyboard = [[KeyboardButton(KEYBOARD_TEXTS["greeting"])]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    # Отправляем приветственное сообщение
    await update.message.reply_text(BOT_TEXTS["greeting"], reply_markup=reply_markup)

# Основная функция для отправки вариантов
async def send_step_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет пользователю варианты для текущего шага."""
    query = update.callback_query or update.message
    chat_id = query.message.chat_id if hasattr(query, "message") else query.chat_id

    # Получаем текущий шаг из user_data
    step = context.user_data.get("step", 1)

    # Создаём инлайн-клавиатуру
    keyboard_texts = sorted(KEYBOARD_TEXTS[str(step)])
    logger.info(keyboard_texts)
    keyboard = [
        [InlineKeyboardButton(keyboard_texts[i], callback_data=f"choice_{step}_{i}")]
        for i in range(len(keyboard_texts))
    ]
    if step > 1:
        keyboard += [[InlineKeyboardButton(KEYBOARD_TEXTS['back'],
                                                     callback_data=f"choice_{step}_666")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с вариантами
    await context.bot.send_message(
        chat_id=chat_id,
        text=BOT_TEXTS[str(step)],
        reply_markup=reply_markup
    )

    # Логирование
    logger.info(f"Пользователю {query.from_user.id} отправлены варианты для шага номер {1}.")

# Основная функция-обработчик
async def handle_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Универсальный обработчик выбора пользователя."""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    step = context.user_data.get("step", 1)

    # Формируем путь к папке
    previous_choices = context.user_data.get("choices", [])
    step_folder = compose_path(step, previous_choices)
    images = sorted([
        img for img in os.listdir(step_folder)
        if img.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    # Получаем выбор пользователя
    choice_index = int(query.data.split("_")[-1])
    choice_step = int(query.data.split("_")[-2])
    logger.info(f"Пользователь {user_id} выбрал ответ с индексом {choice_index} на шаге {step}.")
    if step == choice_step:
        if choice_index == 666:
            logger.info(f"Пользователь вернулся назад. Текущий список выборов  пользователя {context.user_data['choices']}")
            context.user_data["step"] -= 1
            context.user_data["choices"].pop()
            await send_step_options(update, context)
            return

        if step in [1, 2, 4]:
            chosen_image = images[choice_index]
            chosen_path = os.path.join(step_folder, chosen_image)
            logger.info(f"Пользователь {user_id} выбрал файл: {chosen_path} на шаге {step}.")
            context.user_data["choices"].append(os.path.splitext(chosen_image)[0])
            context.user_data["current_path"] = chosen_path
            # Отправляем выбранное изображение
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=open(chosen_path, "rb")
            )
            context.user_data["step"] = step + 1
            logger.info(context.user_data)
            await send_step_options(update, context)
            
        elif step == 3:
            context.user_data["step"] = step + 1
            await send_step_options(update, context)
            return

        elif step == 5: 
            chosen_image = images[choice_index]
            chosen_path = os.path.join(step_folder, chosen_image)
            logger.info(f"Пользователь {user_id} выбрал файл: {chosen_path} на шаге {step}.")
            # Шаги 5-6: создаём изображение
            final_image = create_final_image(
                context.user_data.get("current_path"),
                chosen_path
            )

            # Сохраняем изображение в BytesIO
            final_buffer = BytesIO()
            final_image.save(final_buffer, format="PNG")
            final_buffer.seek(0)

            # Сохраняем в user_data
            context.user_data["img_5_step"] = final_buffer

            # Отправляем изображение пользователю
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=final_buffer
            )
            context.user_data["step"] = step + 1
            logger.info(context.user_data)
            await send_step_options(update, context)

        elif step == 6:
            chosen_image = images[choice_index]
            chosen_path = os.path.join(step_folder, chosen_image)
            logger.info(f"Пользователь {user_id} выбрал файл: {chosen_path} на шаге {step}.")
            # Шаги 5-6: создаём изображение
            final_image = create_final_image(
                context.user_data.get("img_5_step"),
                chosen_path
            )

            # Сохраняем изображение в BytesIO
            final_buffer = BytesIO()
            final_image.save(final_buffer, format="PNG")
            final_buffer.seek(0)

            # Сохраняем в user_data
            context.user_data["img_6_step"] = final_buffer

            # Отправляем изображение пользователю
            message = await context.bot.send_photo(
                chat_id=chat_id,
                photo=final_buffer
            )
            context.user_data["step"] = step + 1
            logger.info(context.user_data)

            keyboard_texts = sorted(KEYBOARD_TEXTS["goodbye"])
            keyboard = \
                    [[InlineKeyboardButton(keyboard_texts[0],
                    switch_inline_query=BOT_TEXTS['message_for_share'])]] + \
                    [[InlineKeyboardButton(keyboard_texts[1], callback_data="promocode")]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=chat_id,
                text=BOT_TEXTS["goodbye"],
                reply_markup=reply_markup
            )

# Финальная функция для показа результата
async def final_step(update: Update, context: ContextTypes.DEFAULT_TYPE, message):
    """Показывает итоговое изображение."""
    user_id = update.callback_query.from_user.id
    chat_id = update.callback_query.message.chat_id

    # Получаем id последнего сообщения
    file_id = message.photo[-1].file_id
    file = await context.bot.get_file(file_id)  
    final_image_url = file.file_path
    context.user_data["final_image_url"] = final_image_url
    keyboard_texts = sorted(KEYBOARD_TEXTS["goodbye"])

    # Кнопка "Поделиться"
    keyboard = \
            [[InlineKeyboardButton(keyboard_texts[0],
            switch_inline_query=f"{final_image_url}")]] + \
            [[InlineKeyboardButton(keyboard_texts[1], callback_data="promocode")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=BOT_TEXTS["goodbye"],
        reply_markup=reply_markup
    )
async def send_promocode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    chat_id = update.callback_query.message.chat_id
    await context.bot.send_message(
        chat_id=chat_id,
        text=BOT_TEXTS["promocode"],
    )
# Основная функция
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT
                                   & filters.Regex(KEYBOARD_TEXTS["greeting"]), send_step_options))
    app.add_handler(CallbackQueryHandler(handle_step, pattern="^choice_"))
    app.add_handler(CallbackQueryHandler(send_promocode, pattern="^promocode$"))
    app.run_polling()

