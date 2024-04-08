import asyncio
import os
import sqlite3
import time
from aiogram import types, Dispatcher, Bot
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import state
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
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


class AnswerRequest(StatesGroup):
    waiting_for_request_id = State()


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
async def select_tag(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик для выбора тега."""
    try:
        tag_id = callback_query.data.split('_')[-1]
        tag_name = cursor.execute("SELECT tag_name FROM Tags WHERE id = ?", (tag_id,)).fetchone()[0]

        async with state.proxy() as data:
            data['tag_id'] = tag_id

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

        if user_requests and any(request[2] != 0 for request in user_requests):
            await bot.send_message(chat_id=user_id, text=response_text, reply_markup=await keyboards.check_my_answer())
        else:
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
async def view_all_requests_callback(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        tag_id = callback_query.data.split('_')[-1]

        # Устанавливаем состояние tag_id
        async with state.proxy() as data:
            data['tag_id'] = tag_id

        cursor.execute("""
            SELECT kr.id, kr.request_text, 
                   (SELECT COUNT(id) FROM KnowledgeResponses WHERE request_id = kr.id) AS num_responses,
                   EXISTS(SELECT 1 FROM KnowledgeResponses WHERE request_id = kr.id) AS has_responses
            FROM KnowledgeRequests kr
            WHERE id_tag = ?
        """, (tag_id,))
        requests = cursor.fetchall()

        if requests:
            response_text = f"Запросы для тега с id {tag_id}:\n"
            for request in requests:
                request_id, request_text, num_responses, has_responses = request
                response_text += f"{request_id}. Запрос: {request_text}\n"
                response_text += f"Количество ответов: {num_responses}\n"
                response_text += "\n"
        else:
            response_text = "Для данного тега пока нет запросов."

        if response_text != "Для данного тега пока нет запросов.":
            await bot.send_message(chat_id=callback_query.from_user.id, text=response_text,
                                   reply_markup=await keyboards.check_answers_and_create_answer(tag_id))
        else:
            await bot.send_message(chat_id=callback_query.from_user.id, text=response_text)
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


@dp.message_handler(state=AnswerRequest.waiting_for_request_id)
async def process_request_id(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            tag_id = data.get('tag_id')

        request_id = int(message.text)

        print(tag_id)
        print(request_id)

        cursor.execute("""
            SELECT kr.id, kr.request_text, t.tag_name
            FROM KnowledgeRequests kr
            LEFT JOIN Tags t ON kr.id_tag = t.id
            WHERE kr.id_tag = ? AND kr.id = ?
        """, (tag_id, request_id))
        request_info = cursor.fetchone()

        print(request_info)

        if request_info:
            request_id, request_text, tag_name = request_info

            cursor.execute("""
                SELECT response_text, author_id
                FROM KnowledgeResponses
                WHERE request_id = ?
            """, (request_id,))
            responses = cursor.fetchall()

            print(responses)

            if responses:
                response_text = (f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                                 f"ID Тега: {tag_id}\n"
                                 f"Название тега: {tag_name}\n"
                                 f"Запрос: {request_text}\n"
                                 f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                                 f"Ответы:\n"
                                 f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n")
                for idx, (temp_response_text, author_id) in enumerate(responses, start=1):
                    response_text += f"Номер ответа: {idx}.\nID Пользователя: {author_id}\nОтвет: {temp_response_text}\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            else:
                response_text = "Нет ответов на данный запрос.\n"

            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("Создать ответ", callback_data=f"create_response_{request_id}"))

            await bot.send_message(chat_id=message.chat.id, text=response_text, reply_markup=keyboard)
        else:
            await bot.send_message(chat_id=message.chat.id, text="Вопрос с указанным номером не найден.")

        await state.finish()

    except ValueError:
        await bot.send_message(chat_id=message.chat.id, text="Неверный формат ввода номера вопроса.")
    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text=f"Произошла ошибка: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith(f'check_answers_'))
async def check_answers(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        tag_id = callback_query.data.split('_')[-1]

        cursor.execute("""
            SELECT DISTINCT request_id FROM KnowledgeResponses
            WHERE request_id IN (
                SELECT id FROM KnowledgeRequests WHERE id_tag = ?
            )
        """, (tag_id,))
        requests_with_answers = cursor.fetchall()

        print(requests_with_answers)

        if requests_with_answers:
            await bot.send_message(chat_id=callback_query.from_user.id,
                                   text="Введите номер вопроса, где вы хотите посмотреть ответы:")
            await AnswerRequest.waiting_for_request_id.set()
        else:
            await bot.send_message(chat_id=callback_query.from_user.id,
                                   text="Нет доступных ответов для данного тега.")
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text=f"Произошла ошибка: {e}")


class AnswerResponse(StatesGroup):
    waiting_for_response_text = State()


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('create_response_'))
async def create_response_callback(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        request_id = callback_query.data.split('_')[-1]

        print(request_id)

        async with state.proxy() as data:
            data['request_id'] = request_id

        await bot.send_message(chat_id=callback_query.from_user.id, text="Введите ваш ответ:")
        await AnswerResponse.waiting_for_response_text.set()

    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


@dp.message_handler(state=AnswerResponse.waiting_for_response_text)
async def create_response(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            request_id = data['request_id']

        response_text = message.text
        author_id = message.from_user.id

        cursor.execute("""
            INSERT INTO KnowledgeResponses (request_id, author_id, response_text) 
            VALUES (?, ?, ?)
        """, (request_id, author_id, response_text))
        conn.commit()

        await bot.send_message(chat_id=message.chat.id, text="Ваш ответ сохранен и отправлен на модерацию")

        await state.finish()

    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text=f"Произошла ошибка: {e}")


if __name__ == '__main__':
    dp.register_message_handler(handler_start, commands=['start'], state='*')
    register.all_callback(dp)
    executor.start_polling(dp, skip_updates=True)
