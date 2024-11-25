import os
import logging
import json
import csv
import pandas as pd
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
        return f"assets/{step-1} ШАГ"
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
            logger.info(f"Пользователь {user_id} перешел к последнему этапу ")
            context.user_data["step"] = step + 1

            keyboard_texts = sorted(KEYBOARD_TEXTS["goodbye"])
            keyboard = \
                    [[InlineKeyboardButton(keyboard_texts[0], switch_inline_query=BOT_TEXTS['message_for_share'])]] + \
                    [[InlineKeyboardButton(keyboard_texts[1],callback_data="promocode")]] + \
                    [[InlineKeyboardButton(keyboard_texts[2], callback_data="lottery")]]

            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=chat_id,
                text=BOT_TEXTS["goodbye"],
                reply_markup=reply_markup
            )

async def send_promocode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    chat_id = update.callback_query.message.chat_id
    logger.info(f"Пользователю {user_id} отправлен промокод")
    await context.bot.send_message(
        chat_id=chat_id,
        text=BOT_TEXTS["promocode"],
    )

async def join_lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.callback_query.message.chat_id
    user = update.callback_query.from_user
    username = user.username
    user_id = user.id

    lottery_data_path = 'lottery_data.xlsx'

    # Данные для проверки и добавления
    data = {"username": [username], "user_id": [user_id]}

    # Преобразуем список словарей в DataFrame
    new_df = pd.DataFrame(data)

    # Проверяем, существует ли файл
    if os.path.exists(lottery_data_path):
        # Читаем существующие данные
        existing_data = pd.read_excel(lottery_data_path)

        # Проверяем, есть ли новые данные в существующих
        merged_data = pd.merge(new_df, existing_data, how='inner')
        if not merged_data.empty:
            logger.info(f"Пользователь {username} уже есть в списке участников")
        else:
            # Добавляем данные в конец
            updated_data = pd.concat([existing_data, new_df], ignore_index=True)
            updated_data.to_excel(lottery_data_path, index=False)
            logger.info(f"Пользователь {username} добавлен в список участников")
    else:
        # Если файла нет, создаем новый с данными
        new_df.to_excel(lottery_data_path, index=False)
        logger.info(f"Создан файл с данными для конкурса {lottery_data_path}")

    await context.bot.send_message(
        chat_id=chat_id,
        text=BOT_TEXTS["lottery"],
    )

# Основная функция
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT
                                   & filters.Regex(KEYBOARD_TEXTS["greeting"]), send_step_options))
    app.add_handler(CallbackQueryHandler(handle_step, pattern="^choice_"))
    app.add_handler(CallbackQueryHandler(send_promocode, pattern="^promocode$"))
    app.add_handler(CallbackQueryHandler(join_lottery, pattern="^lottery$"))
    app.run_polling()

