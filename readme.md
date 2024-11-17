# Telegram Bot: Создание Уникальных Открыток

Этот проект представляет собой Telegram-бота, который позволяет пользователю поэтапно создавать уникальную открытку, комбинируя изображения из заранее подготовленных шаблонов. Бот предоставляет простой и интуитивно понятный интерфейс с изображениями выбора и inline-кнопками для управления.

---

## Установка

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/goingbraindeadisolated/visit-card-generator-bot
cd visit-card-generator-bot
```

### 2. Настройте виртуальное окружение
Создайте и активируйте виртуальное окружение:
```bash
python3 -m venv venv
source venv/bin/activate   # Для macOS/Linux
venv\Scripts\activate      # Для Windows
```

### 3. Установите зависимости
```bash
pip install -r requirements.txt
```

### 4. Настройте токен Telegram-бота
1. Создайте бота в Telegram через [BotFather](https://t.me/botfather).
2. Скопируйте токен вашего бота.
3. Создайте файл `.env` в корне проекта и добавьте токен:
   ```env
   TELEGRAM_BOT_TOKEN=ваш_токен_бота
   ```


## Использование

### 1. Запустите бота
Активируйте виртуальное окружение (если ещё не активировано) и выполните:
```bash
python bot.py
```

### 2. Начните работу в Telegram
1. Найдите вашего бота в Telegram, используя его имя.
2. Введите `/start`, чтобы начать процесс создания открытки.
3. Следуйте инструкциям:
   - Выбирайте элементы на каждом этапе, нажимая на соответствующие кнопки.
   - Используйте кнопку "Назад", если хотите изменить выбор.

---

## Основные компоненты

- **bot.py** — основной файл бота.
- **assets/** — папка с исходными изображениями для всех этапов.
- **requirements.txt** — файл зависимостей.

---

## Технологии

- **Python** — язык программирования.
- **python-telegram-bot** — библиотека для создания Telegram-ботов.
- **Pillow (PIL)** — библиотека для обработки изображений.

---

## Поддержка

Если у вас есть вопросы или предложения, вы можете связаться с автором проекта через its.renatt@gmail.com.

---

