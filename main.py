import asyncio
import os
import sqlite3
import time
from aiogram import types, Dispatcher, Bot
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.types import ParseMode
from aiogram.utils import executor
import pytz
import config
import keyboards
import register
import sms
from datetime import datetime
from aiogram.dispatcher import FSMContext
from states import EnterRequestText

bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())
conn = sqlite3.connect('database.db')
cursor = conn.cursor()


@dp.message_handler(commands=['start'], state='*')
async def handler_start(message: types.Message, state: FSMContext):
    verify = cursor.execute('SELECT * FROM Users WHERE id =?', (message.from_user.id,)).fetchone()
    if not verify:
        await bot.send_message(chat_id=message.from_user.id,
                               text=sms.message_start())
        await bot.send_message(chat_id=message.from_user.id, text=sms.register_start())

        await bot.send_message(chat_id=message.from_user.id, text=sms.need_notification_or_not(),
                               reply_markup=await keyboards.need_notification_or_not())
    else:
        await bot.send_message(chat_id=message.from_user.id, text=sms.profile_user(message.from_user.id),
                               reply_markup=await keyboards.main_menu())


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('select_tag_'))
async def select_tag(callback_query: types.CallbackQuery):
    """Обработчик для выбора тега."""
    try:
        tag_id = callback_query.data.split('_')[-1]
        tag_name = cursor.execute("SELECT tag_name FROM Tags WHERE id = ?", (tag_id,)).fetchone()[0]

        await bot.send_message(chat_id=callback_query.from_user.id, text=sms.get_tag(tag_name),
                               reply_markup=await keyboards.button_for_tags(tag_id))
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text=f"Произошла ошибка: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('my_requests_'))
async def my_requests(callback_query: types.CallbackQuery):
    """Обработчик для просмотра запросов пользователя."""
    try:
        user_id = callback_query.from_user.id
        tag_id = callback_query.data.split('_')[-1]

        cursor.execute("""
            SELECT request_text, request_media, votes, timestamp, moderated 
            FROM KnowledgeRequests 
            WHERE id_tag = ? AND author_id = ?
        """, (tag_id, user_id))

        user_requests = cursor.fetchall()

        if user_requests:
            response_text = "Ваши запросы:\n"
            for idx, request in enumerate(user_requests, start=1):
                request_text, request_media, votes, timestamp, moderated = request
                response_text += f"Запрос: {request_text}\n"
                response_text += f"Номер запроса: {idx}\n"
                if request_media:
                    response_text += f"Медиа: {request_media}\n"
                response_text += f"Голоса: {votes}\n"
                response_text += f"Время создания: {timestamp}\n"
                response_text += f"Модерировано: {'Да' if moderated else 'Нет'}\n\n"
        else:
            response_text = "У вас пока нет запросов по данному тегу."

        await bot.send_message(chat_id=user_id, text=response_text)
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text=f"Произошла ошибка: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('create_request_'), state='*')
async def create_request(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик для создания нового запроса."""
    try:
        tag_id = callback_query.data.split('_')[-1]

        await state.update_data(tag_id=tag_id)
        await EnterRequestText.waiting_for_request_text.set()

        await bot.send_message(chat_id=callback_query.from_user.id,
                               text="Введите текст нового запроса:")
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text=f"Произошла ошибка: {e}")


@dp.message_handler(state=EnterRequestText.waiting_for_request_text)
async def process_request_text(message: types.Message, state: FSMContext):
    """Обработчик для текста нового запроса."""
    try:
        request_text = message.text.strip()

        async with state.proxy() as data:
            tag_id = data['tag_id']

        cursor.execute("INSERT INTO KnowledgeRequests (author_id, request_text, id_tag) VALUES (?, ?, ?)",
                       (message.from_user.id, request_text, tag_id))
        conn.commit()

        await message.answer("Запрос успешно добавлен!")

        await state.finish()

    except Exception as e:
        await message.answer(f"Произошла ошибка при добавлении запроса: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('view_all_requests_'))
async def view_all_requests(callback_query: types.CallbackQuery):
    try:
        tag_id = callback_query.data.split('_')[-1]

        # Получаем все запросы для данного тега
        cursor.execute("""
            SELECT id, request_text, (SELECT COUNT(id) FROM KnowledgeResponses WHERE request_id = kr.id) AS num_responses
            FROM KnowledgeRequests kr
            WHERE id_tag = ?
        """, (tag_id,))

        requests = cursor.fetchall()

        if requests:
            response_text = f"Запросы для тега с id {tag_id}:\n"
            for idx, request in enumerate(requests, start=1):
                request_id, request_text, num_responses = request
                response_text += f"{idx}. Запрос: {request_text}\n"
                response_text += f"Количество ответов: {num_responses}\n"
                response_text += f"{'Посмотреть ответы' if num_responses > 0 else ''}\n\n"
        else:
            response_text = "Для данного тега пока нет запросов."

        await bot.send_message(chat_id=callback_query.from_user.id, text=response_text)
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


if __name__ == '__main__':
    dp.register_message_handler(handler_start, commands=['start'], state='*')
    register.all_callback(dp)
    executor.start_polling(dp, skip_updates=True)
