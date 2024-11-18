import logging
import uuid
import asyncio
import re
import requests
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    InlineQueryHandler,
)
from simpleeval import simple_eval  # Библиотека для безопасного вычисления выражений
from langdetect import detect

# Устанавливаем уровень логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Ваш API ключ для прокси-сервиса
PROXY_API_KEY = 'sk-bmo4E1WU4cCJVY79L8DfY8pjl082Wtdb'  # Замените на ваш реальный ключ

# URL прокси-сервера
OPENAI_PROXY_URL = 'https://api.proxyapi.ru/openai/v1/chat/completions'

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

def detect_wrong_layout(text):
    ru_letters = sum(1 for c in text if 'а' <= c.lower() <= 'я' or c.lower() == 'ё')
    en_letters = sum(1 for c in text if 'a' <= c.lower() <= 'z')
    # Если есть английские буквы, но нет русских
    if ru_letters == 0 and en_letters > 0:
        return 'to_ru'
    # Если есть русские буквы, но нет английских
    elif en_letters == 0 and ru_letters > 0:
        return 'to_en'
    else:
        # Не менять раскладку
        return None

def change_layout(text, to_layout):
    if to_layout == 'ru':
        return text.translate(EN_TO_RU)
    elif to_layout == 'en':
        return text.translate(RU_TO_EN)
    else:
        return text

def is_math_expression(text):
    # Проверка на наличие допустимых символов в математическом выражении
    pattern = r'^[\d\s\+\-\*/\(\)\.\,]+$'
    return bool(re.match(pattern, text))

def evaluate_expression(expr):
    try:
        # Вычисляем выражение безопасно
        result = str(simple_eval(expr))
        return result
    except Exception as e:
        return f"Ошибка вычисления: {e}"

async def get_openai_response(messages):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {PROXY_API_KEY}',
    }
    data = {
        'model': 'gpt-4o-mini',
        'messages': messages,
        'n': 1,
        'max_tokens': 250,
        'temperature': 0.7,
    }
    try:
        # Отправляем запрос
        response = await asyncio.to_thread(
            requests.post,
            OPENAI_PROXY_URL,
            headers=headers,
            json=data,
            timeout=15
        )
        response.raise_for_status()
        result = response.json()
        return [choice['message']['content'].strip() for choice in result.get('choices', [])]
    except Exception as e:
        logging.error(f"Ошибка при обращении к OpenAI API: {e}")
        return ["Произошла ошибка при обращении к OpenAI API. Пожалуйста, попробуйте позже."]

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query:
        return

    suggestions = []

    # Проверяем префиксы режимов
    if query.startswith('calc:'):
        expr = query[len('calc:'):].strip()
        result = evaluate_expression(expr)
        suggestions = [f"{expr} = {result}"]
    elif query.startswith('key:'):
        text = query[len('key:'):].strip()
        wrong_layout = detect_wrong_layout(text)
        if wrong_layout == 'to_ru':
            corrected_text = change_layout(text, 'ru')
        elif wrong_layout == 'to_en':
            corrected_text = change_layout(text, 'en')
        else:
            corrected_text = text
        suggestions = [corrected_text]
    elif query.startswith('translate:'):
        text = query[len('translate:'):].strip()
        try:
            input_lang = detect(text)
        except:
            input_lang = 'unknown'
        
        # Определяем язык перевода
        if input_lang == 'ru':
            target_lang = 'English'
            detected_lang = 'Русский'
        elif input_lang == 'en':
            target_lang = 'Russian'
            detected_lang = 'Английский'
        else:
            target_lang = 'Russian'
            detected_lang = 'Неизвестно'

        # Формируем системную инструкцию
        system_message = f"Переведи этот текст на {target_lang}:"

        # Подготовка сообщений для OpenAI
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": text}
        ]

        # Получаем перевод от OpenAI
        suggestions = await get_openai_response(messages)
        # Добавляем информацию о определенном языке
        suggestions = [f"{suggestions[0]}"]
    elif query.startswith('neuro:'):
        text = query[len('neuro:'):].strip()
        # Используем OpenAI для генерации ответа
        system_message = (
            "Ты интеллектуальный помощник, который отвечает на вопросы и помогает пользователям. "
            "Всегда отвечай на русском языке."
        )
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": text}
        ]
        suggestions = await get_openai_response(messages)
    else:
        suggestions = ['Пожалуйста, выберите режим и введите запрос в формате:',
                       'calc: выражение для вычисления',
                       'key: текст для исправления раскладки',
                       'translate: текст для перевода',
                       'neuro: ваш запрос']
        # Формируем результаты для инлайн-ответа
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=suggestion,
                input_message_content=InputTextMessageContent(suggestion),
                description=suggestion
            ) for suggestion in suggestions
        ]
        # Отправляем инструкции пользователю
        await update.inline_query.answer(results, cache_time=0)
        return

    # Формируем результаты для инлайн-ответа
    results = []

    for suggestion in suggestions:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=suggestion[:50],  # Первые 50 символов для заголовка
                input_message_content=InputTextMessageContent(suggestion),
                description=suggestion
            )
        )

    # Отправляем инлайн-ответ пользователю
    await update.inline_query.answer(results, cache_time=0)

def main():
    # Замените 'YOUR_BOT_TOKEN' на токен вашего бота
    application = ApplicationBuilder().token('7770305165:AAFb1C9DcLiZaYGwY4J7ZynM4NzmpyiCspw').build()

    # Добавляем обработчик инлайн запросов
    application.add_handler(InlineQueryHandler(inline_query))

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()
