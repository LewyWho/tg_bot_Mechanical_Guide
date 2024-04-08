import asyncio
import os
import sqlite3
import time
from aiogram import types, Dispatcher, Bot
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
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
from states import AnswerRequest

bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

CURRENT_PAGE = 1
TOTAL_PAGES = 1


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
async def view_all_requests_callback(callback_query: types.CallbackQuery):
    try:
        tag_id = callback_query.data.split('_')[-1]

        if not hasattr(view_all_requests_callback, 'requests'):  # Проверяем, были ли запросы уже получены
            # Если нет, то получаем запросы из базы данных
            cursor.execute("""
                SELECT kr.id, kr.request_text, 
                       (SELECT COUNT(id) FROM KnowledgeResponses WHERE request_id = kr.id) AS num_responses,
                       EXISTS(SELECT 1 FROM KnowledgeResponses WHERE request_id = kr.id) AS has_responses
                FROM KnowledgeRequests kr
                WHERE id_tag = ?
            """, (tag_id,))
            view_all_requests_callback.requests = cursor.fetchall()

        requests = view_all_requests_callback.requests

        if requests:
            global TOTAL_PAGES
            TOTAL_PAGES = (len(requests) + 4) // 5  # Определяем общее количество страниц

            response_text = f"Запросы для тега с id {requests[0][2]}:\n"  # Исправлено здесь
            start_idx = (CURRENT_PAGE - 1) * 5
            end_idx = min(start_idx + 5, len(requests))
            for idx, request in enumerate(requests[start_idx:end_idx], start=start_idx + 1):
                request_id, request_text, num_responses, has_responses = request
                response_text += f"{idx}. Запрос: {request_text}\n"
                response_text += f"Количество ответов: {num_responses}\n"
                response_text += "\n"
        else:
            response_text = "Для данного тега пока нет запросов."

        await send_requests_with_buttons(callback_query.from_user.id, response_text, tag_id)
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


async def send_requests_with_buttons(user_id, response_text, tag_id):
    """Отправляет сообщение с запросами и кнопками навигации."""
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = []

    buttons.append(
        InlineKeyboardButton(text="Посмотреть ответы/Ответить на запрос", callback_data=f"respond_to_request_{tag_id}"))

    if CURRENT_PAGE > 1:
        buttons.append(InlineKeyboardButton(text="Назад", callback_data="back_page_requests"))

    if CURRENT_PAGE < TOTAL_PAGES:
        buttons.append(InlineKeyboardButton(text="Вперед", callback_data="next_page_requests"))

    keyboard.add(*buttons)
    await bot.send_message(chat_id=user_id, text=response_text, reply_markup=keyboard)


@dp.callback_query_handler(text="back_page_requests")
async def back_page_requests(callback_query: types.CallbackQuery):
    """Обработчик для кнопки 'Назад' к запросам."""
    try:
        global CURRENT_PAGE
        if CURRENT_PAGE > 1:
            CURRENT_PAGE -= 1
            await view_all_requests_callback(callback_query)
        else:
            await bot.send_message(chat_id=callback_query.from_user.id, text="Это первая страница.")
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


@dp.callback_query_handler(text="next_page_requests")
async def next_page_requests(callback_query: types.CallbackQuery):
    """Обработчик для кнопки 'Вперед' к запросам."""
    try:
        global CURRENT_PAGE, TOTAL_PAGES
        if CURRENT_PAGE < TOTAL_PAGES:
            CURRENT_PAGE += 1
            await view_all_requests_callback(callback_query)
        else:
            await bot.send_message(chat_id=callback_query.from_user.id, text="Это последняя страница.")
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('respond_to_request_'))
async def respond_to_request(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        # Получаем id тега из данных callback'а
        tag_id = callback_query.data.split('_')[-1]

        # Сохраняем id тега в состояние
        await state.update_data(tag_id=tag_id)

        # Отправляем запрос на ввод номера вопроса
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text="Введите номер вопроса, для которого вы хотите посмотреть ответы/Оставить свой ответ")

        # Устанавливаем состояние ожидания ввода номера вопроса
        await AnswerRequest.waiting_for_request_id.set()

    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")

@dp.message_handler(state=AnswerRequest.waiting_for_request_id)
async def process_request_id(message: types.Message, state: FSMContext):
    try:
        # Получаем id тега из состояния
        data = await state.get_data()
        tag_id = data.get('tag_id')

        request_id = message.text

        # Получение информации о выбранном запросе из базы данных
        cursor.execute("""
            SELECT kr.id, kr.request_text, t.tag_name
            FROM KnowledgeRequests kr
            LEFT JOIN Tags t ON kr.id_tag = t.id
            WHERE kr.id = ? AND kr.id_tag = ?
        """, (request_id, tag_id))
        request_info = cursor.fetchone()

        if request_info:
            request_id, request_text, tag_name = request_info

            response_text = f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\nID Тега: {request_id}\nНазвание тега: {tag_name}\nЗапрос: {request_text}\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n\nОтветы:\n"

            # Получение всех ответов на данный запрос из базы данных
            cursor.execute("""
                SELECT response_text
                FROM KnowledgeResponses
                WHERE request_id = ?
            """, (request_id,))
            responses = cursor.fetchall()

            if responses:
                for idx, (response_text,) in enumerate(responses, start=1):
                    response_text += f"{idx}. Ответ: {response_text}\n"
            else:
                response_text += "Нет ответов на данный запрос.\n"

            await bot.send_message(chat_id=message.chat.id, text=response_text)

        else:
            await bot.send_message(chat_id=message.chat.id, text="Вопрос с таким номером не найден.")

        # Сбрасываем состояние
        await state.finish()

    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text=f"Произошла ошибка: {e}")


if __name__ == '__main__':
    dp.register_message_handler(handler_start, commands=['start'], state='*')
    register.all_callback(dp)
    executor.start_polling(dp, skip_updates=True)
