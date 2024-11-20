import os
import logging
import json
import csv
from dotenv import load_dotenv
from io import BytesIO
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters
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
    keyboard = [
        [InlineKeyboardButton(keyboard_texts[i], callback_data=f"choice_{i}")]
        for i in range(len(keyboard_texts))
    ]
    if step > 1:
        keyboard += [[InlineKeyboardButton(KEYBOARD_TEXTS['back'],
                                                     callback_data="choice_666")]]
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

    # Текущий шаг
    step = context.user_data.get("step", 1)
    previous_choices = context.user_data.get("choices", [])

    if step == 3:
        context.user_data["step"] = step + 1
        await send_step_options(update, context)
        return

    # Формируем путь к папке
    step_folder = compose_path(step, previous_choices)
    images = sorted([
        img for img in os.listdir(step_folder)
        if img.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    # Получаем выбор пользователя
    choice_index = int(query.data.split("_")[-1])
    if choice_index == 666:
        logger.info(f"Пользователь вернулся назад. Текущий список выборов  пользователя {context.user_data['choices']}")
        context.user_data["step"] -= 1
        context.user_data["choices"].pop()
        await send_step_options(update, context)
    else:
        logger.info(f"Пользователь {user_id} выбрал ответ с индексом {choice_index} на шаге {step}.")
        chosen_image = images[choice_index]
        chosen_path = os.path.join(step_folder, chosen_image)

        # Логируем выбор
        logger.info(f"Пользователь {user_id} выбрал файл: {chosen_path} на шаге {step}.")

        # Обработка изображения
        if step in [1, 2, 4]:
            # Шаги 1-3: сохраняем выбор и добавляем путь к user_data
            context.user_data["choices"].append(os.path.splitext(chosen_image)[0])
            context.user_data["current_image"] = chosen_path

            # Отправляем выбранное изображение
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=open(chosen_path, "rb")
            )
        else: 
            # Шаги 5-6: создаём изображение
            final_image = create_final_image(
                context.user_data.get("current_image"),
                chosen_path
            )

            # Сохраняем изображение в BytesIO
            final_buffer = BytesIO()
            final_image.save(final_buffer, format="PNG")
            final_buffer.seek(0)

            # Сохраняем в user_data
            context.user_data["current_image"] = final_buffer

            # Отправляем изображение пользователю
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=final_buffer
            )

        # Переход к следующему шагу или завершение
        if step <= 5:
            context.user_data["step"] = step + 1
            logger.info(context.user_data)
            await send_step_options(update, context)
        else:
            await query.answer("Создание завершено!")
            await show_final_result(update, context)

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

# Финальная функция для показа результата
async def show_final_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает итоговое изображение."""
    user_id = update.callback_query.from_user.id
    chat_id = update.callback_query.message.chat_id

    # Извлекаем изображение из user_data
    final_buffer = context.user_data.get("current_image")
    if not final_buffer:
        logger.error(f"У пользователя {user_id} отсутствует итоговое изображение.")
        await context.bot.send_message(
            chat_id=chat_id,
            text=BOT_TEXTS["error_no_final_image"]
        )
        return

    # Отправляем изображение
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=final_buffer,
        caption=BOT_TEXTS["final_result"]
    )

    # Кнопка "Поделиться"
    keyboard = [[InlineKeyboardButton(BOT_TEXTS["share_button"], switch_inline_query="Посмотрите мою открытку!")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=BOT_TEXTS["share_prompt"],
        reply_markup=reply_markup
    )

# Основная функция
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT
                                   & filters.Regex(KEYBOARD_TEXTS["greeting"]), send_step_options))
    app.add_handler(CallbackQueryHandler(handle_step, pattern="^choice_"))
    app.run_polling()

