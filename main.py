import logging
import uuid
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    InlineQueryHandler,
)

# Устанавливаем уровень логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Создаем списки символов для английской и русской раскладок
EN_CHARS = (
    '`', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', 'a', 's',
    'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'", 'z', 'x', 'c', 'v', 'b', 'n',
    'm', ',', '.', '/', '~', '@', '#', '$', '^', '&', 'Q', 'W', 'E', 'R', 'T',
    'Y', 'U', 'I', 'O', 'P', '{', '}', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K',
    'L', ':', '"', '|', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<', '>', '?'
)

RU_CHARS = (
    'ё', 'й', 'ц', 'у', 'к', 'е', 'н', 'г', 'ш', 'щ', 'з', 'х', 'ъ', 'ф', 'ы',
    'в', 'а', 'п', 'р', 'о', 'л', 'д', 'ж', 'э', 'я', 'ч', 'с', 'м', 'и', 'т',
    'ь', 'б', 'ю', '.', 'Ё', '"', '№', ';', ':', '?', 'Й', 'Ц', 'У', 'К', 'Е',
    'Н', 'Г', 'Ш', 'Щ', 'З', 'Х', 'Ъ', 'Ф', 'Ы', 'В', 'А', 'П', 'Р', 'О', 'Л',
    'Д', 'Ж', 'Э', '/', 'Я', 'Ч', 'С', 'М', 'И', 'Т', 'Ь', 'Б', 'Ю', ','
)

# Проверяем, что длины совпадают
assert len(EN_CHARS) == len(RU_CHARS), "Длины EN_CHARS и RU_CHARS должны совпадать"

# Создаем таблицы перевода
EN_TO_RU = {ord(en_char): ru_char for en_char, ru_char in zip(EN_CHARS, RU_CHARS)}
RU_TO_EN = {ord(ru_char): en_char for en_char, ru_char in zip(EN_CHARS, RU_CHARS)}

def detect_layout(text):
    ru_letters = sum(1 for c in text if 'а' <= c.lower() <= 'я' or c in 'ёЁ')
    en_letters = sum(1 for c in text if 'a' <= c.lower() <= 'z')
    if en_letters > ru_letters:
        return 'en'
    elif ru_letters > en_letters:
        return 'ru'
    else:
        return None

def change_layout(text, to_layout):
    if to_layout == 'ru':
        return text.translate(EN_TO_RU)
    elif to_layout == 'en':
        return text.translate(RU_TO_EN)
    else:
        return text

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query:
        return

    current_layout = detect_layout(query)
    if current_layout == 'en':
        corrected_text = change_layout(query, 'ru')
        layout_message = "Похоже, вы набрали текст в английской раскладке. Исправить?"
    elif current_layout == 'ru':
        corrected_text = change_layout(query, 'en')
        layout_message = "Похоже, вы набрали текст в русской раскладке. Исправить?"
    else:
        corrected_text = query
        layout_message = "Не удалось определить раскладку. Оставить текст без изменений?"

    results = [
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title=layout_message,
            input_message_content=InputTextMessageContent(corrected_text),
            description=corrected_text
        ),
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="Оставить как есть",
            input_message_content=InputTextMessageContent(query),
            description=query
        )
    ]

    await update.inline_query.answer(results, cache_time=0)

def main():
    # Замените 'YOUR_TOKEN_HERE' на токен вашего бота
    application = ApplicationBuilder().token('7770305165:AAFb1C9DcLiZaYGwY4J7ZynM4NzmpyiCspw').build()

    # Добавляем обработчик инлайн запросов
    application.add_handler(InlineQueryHandler(inline_query))

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()
