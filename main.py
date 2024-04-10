import asyncio
import os
import sqlite3
import time
from collections import defaultdict

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
    waiting_for_response_id = State()


class ChangeAnswer(StatesGroup):
    waiting_for_question_number = State()
    waiting_for_new_answer = State()


class ChangeQuestion(StatesGroup):
    waiting_for_question_number = State()
    waiting_for_new_question = State()


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


@dp.message_handler(commands=['users'], state='*')
async def handler_users(message: types.Message, state: FSMContext):
    cursor.execute("""
        SELECT u.id, u.username, u.rank_user, COUNT(DISTINCT kr.id) AS total_responses, COUNT(DISTINCT rq.id) AS total_requests
        FROM Users u
        LEFT JOIN KnowledgeResponses kr ON u.id = kr.author_id
        LEFT JOIN KnowledgeRequests rq ON u.id = rq.author_id
        GROUP BY u.id, u.username, u.rank_user
    """)
    users_data = cursor.fetchall()

    temp_file_path = "users.txt"
    with open(temp_file_path, "w", encoding="utf-8") as file:
        users_message = "Список пользователей:\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        for user_id, username, rank_user, total_responses, total_requests in users_data:
            if not username:
                username = "неизвестно"
            if username == "неизвестно":
                username = "неизвестно"
            else:
                username = f"@{username}"
            users_message += f"ID: {user_id}\n" \
                             f"Имя пользователя: {username}\n" \
                             f"Ранг: {rank_user}\n" \
                             f"Запросов на знания: {total_requests}\n" \
                             f"Ответов: {total_responses}\n" \
                             "➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            file.write(users_message)

    if len(users_data) > 15:
        with open(temp_file_path, "rb") as file:
            await message.answer_document(file)
        os.remove(temp_file_path)
    else:
        await message.answer(users_message)


@dp.message_handler(commands=['cancel'], state='*')
async def cancel_operation(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Операция отменена.")


@dp.message_handler(commands=['a_change'], state='*')
async def handler_a_change(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    cursor.execute("""
        SELECT kr.id, kr.request_id, kr.response_text, kr.response_media, rq.request_text, t.tag_name
        FROM KnowledgeResponses kr
        JOIN KnowledgeRequests rq ON kr.request_id = rq.id
        JOIN Tags t ON rq.id_tag = t.id
        WHERE kr.author_id=?
    """, (user_id,))
    user_responses = cursor.fetchall()
    if not user_responses:
        await message.answer("У вас нет ни одного ответа для изменения.")
        return

    for index, response in enumerate(user_responses, start=1):
        response_message = f"{index}. Запрос: {response[4]}\nТег: {response[5]}\nОтвет: {response[2]}\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        if response[3]:
            media_file_id = response[3]
            if media_file_id.startswith("AgAC"):
                await bot.send_photo(chat_id=message.chat.id, photo=media_file_id, caption=response_message)
            elif media_file_id.startswith("BAAC"):
                await bot.send_video(chat_id=message.chat.id, video=media_file_id, caption=response_message)
            elif media_file_id.startswith("AwAC"):
                await bot.send_voice(chat_id=message.chat.id, voice=media_file_id, caption=response_message)
            elif media_file_id.startswith("BQAC"):
                await bot.send_document(chat_id=message.chat.id, document=media_file_id, caption=response_message)
            elif media_file_id.startswith("DQAC"):
                await bot.send_message(chat_id=message.chat.id, text=response_message)
                await bot.send_video_note(chat_id=message.chat.id, video_note=media_file_id)
        else:
            await message.answer(response_message)

    await message.answer(
        "Выберите номер ответа, который вы хотите изменить\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n/cancel - для отмены\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n")

    await ChangeAnswer.waiting_for_question_number.set()


@dp.message_handler(state=ChangeAnswer.waiting_for_question_number, content_types=[
    types.ContentType.TEXT,
    types.ContentType.DOCUMENT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.VOICE,
    types.ContentType.VIDEO_NOTE
])
async def process_question_number(message: types.Message, state: FSMContext):
    try:
        question_number = int(message.text)
    except ValueError:
        await message.answer("Пожалуйста, введите корректный номер вопроса.")
        return

    async with state.proxy() as data:
        data['question_number'] = question_number

    await message.answer("Введите ваш новый ответ:")

    await ChangeAnswer.waiting_for_new_answer.set()


# Обработка медиа-файлов в ответах пользователя
@dp.message_handler(state=ChangeAnswer.waiting_for_new_answer, content_types=[
    types.ContentType.TEXT,
    types.ContentType.DOCUMENT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.VOICE,
    types.ContentType.VIDEO_NOTE
])
async def process_new_answer(message: types.Message, state: FSMContext):
    new_answer = message.text

    async with state.proxy() as data:
        user_id = message.from_user.id
        question_number = data['question_number']

    media_file_id = None

    if message.photo:
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_file_id = message.video.file_id
    elif message.voice:
        media_file_id = message.voice.file_id
    elif message.document:
        media_file_id = message.document.file_id
    elif message.video_note:
        media_file_id = message.video_note.file_id
    elif message.text:
        if not new_answer:
            await message.answer("Вы не ввели новый ответ.")
            return

    cursor.execute(
        "UPDATE KnowledgeResponses SET response_text=?, response_media=?, moderated=0 WHERE id=? AND author_id=?",
        (new_answer, media_file_id, question_number, user_id))
    conn.commit()

    await message.answer("Ответ успешно изменен и отправлен на проверку.")
    await state.finish()


@dp.message_handler(commands=['q_change'], state='*')
async def handler_q_change(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    cursor.execute("""
        SELECT kr.id, kr.request_text, kr.request_media, kr.id_tag, t.tag_name
        FROM KnowledgeRequests kr
        JOIN Tags t ON kr.id_tag = t.id
        WHERE kr.author_id=?
    """, (user_id,))
    user_questions = cursor.fetchall()
    if not user_questions:
        await message.answer("У вас нет ни одного вопроса для изменения.")
        return

    for index, question in enumerate(user_questions, start=1):
        question_message = f"{index}. Ваш вопрос: {question[1]}\nТег: {question[4]}\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        if question[2]:
            media_file_id = question[2]
            if media_file_id.startswith("AgAC"):
                await bot.send_photo(chat_id=message.chat.id, photo=media_file_id, caption=question_message)
            elif media_file_id.startswith("BAAC"):
                await bot.send_video(chat_id=message.chat.id, video=media_file_id, caption=question_message)
            elif media_file_id.startswith("AwAC"):
                await bot.send_voice(chat_id=message.chat.id, voice=media_file_id, caption=question_message)
            elif media_file_id.startswith("BQAC"):
                await bot.send_document(chat_id=message.chat.id, document=media_file_id, caption=question_message)
            elif media_file_id.startswith("DQAC"):
                await bot.send_message(chat_id=message.chat.id, text=question_message)
                await bot.send_video_note(chat_id=message.chat.id, video_note=media_file_id)
        else:
            await message.answer(question_message)

    await message.answer(
        "Выберите номер вопроса, который вы хотите изменить\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n/cancel - для отмены\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n")

    await ChangeQuestion.waiting_for_question_number.set()


@dp.message_handler(state=ChangeQuestion.waiting_for_question_number, content_types=[
    types.ContentType.TEXT,
    types.ContentType.DOCUMENT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.VOICE,
    types.ContentType.VIDEO_NOTE
])
async def process_question_number(message: types.Message, state: FSMContext):
    try:
        question_number = int(message.text)
    except ValueError:
        await message.answer("Пожалуйста, введите корректный номер вопроса.")
        return
    async with state.proxy() as data:
        data['question_number'] = question_number
    await message.answer("Введите ваш новый вопрос:")
    await ChangeQuestion.waiting_for_new_question.set()


@dp.message_handler(state=ChangeQuestion.waiting_for_new_question, content_types=[
    types.ContentType.TEXT,
    types.ContentType.DOCUMENT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.VOICE,
    types.ContentType.VIDEO_NOTE
])
async def process_new_question(message: types.Message, state: FSMContext):
    new_question = message.text
    media_file_id = None

    if message.photo:
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_file_id = message.video.file_id
    elif message.voice:
        media_file_id = message.voice.file_id
    elif message.document:
        media_file_id = message.document.file_id
    elif message.video_note:
        media_file_id = message.video_note.file_id

    if not new_question and not media_file_id:
        await message.answer("Вы не ввели новый вопрос или не прикрепили медиафайл.")
        return

    async with state.proxy() as data:
        user_id = message.from_user.id
        question_number = data['question_number']

    cursor.execute(
        "UPDATE KnowledgeRequests SET request_text=?, request_media=?, moderated=0 WHERE id=? AND author_id=?",
        (new_question, media_file_id, question_number, user_id))
    conn.commit()
    await message.answer("Вопрос успешно изменен и отправлен на проверку.")
    await state.finish()


@dp.message_handler(commands=['cancel'], state='*')
async def cancel_operation(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Операция отменена.")


@dp.message_handler(commands=['help'], state='*')
async def handler_help(message: types.Message):
    await message.answer(sms.help_message())


@dp.message_handler(commands=['sms'], state='*')
async def send_message_to_user(message: types.Message):
    try:
        from_user_id = message.from_user.id

        command_args = message.get_args().split()
        if len(command_args) < 2:
            await message.reply("Неверный формат команды. Используйте /sms {user_id} {текст}")
            return

        user_id = int(command_args[0])
        text = ' '.join(command_args[1:])

        verify_try = cursor.execute("SELECT needed_sms_for_user FROM Users WHERE id =?", (user_id,)).fetchone()[0]

        user = await bot.get_chat(user_id)
        if user:
            if verify_try == 1:
                await bot.send_message(user_id,
                                       f"Сообщение от пользователя.\nID пользователя: {from_user_id}\nТекст: {text}")
                await message.reply("Сообщение успешно отправлено.")
            else:
                await message.reply("Пользователь отключил функцию получения сообщений.")
        else:
            await message.reply("Пользователь с указанным ID не найден.")

    except Exception as e:
        await message.reply(f"Произошла ошибка: {e}")


@dp.message_handler(commands=['my_settings'], state='*')
async def my_settings(message: types.Message):
    user_id = message.from_user.id

    cursor.execute("SELECT needed_sms_for_user, notification_preferences FROM Users WHERE id=?", (user_id,))
    settings = cursor.fetchone()

    needed_sms_for_user, notification_preferences = settings

    text = "➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
    if needed_sms_for_user == 0:
        text += "На данный момент вы не хотите получать сообщения от пользователей.\n"
    else:
        text += "На данный момент вы получаете сообщения от пользователей.\n"
    text += "➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
    text += "Хотите ли вы получать сообщения от пользователей?\n"
    text += '➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'

    keyboard_sms = InlineKeyboardMarkup()
    if needed_sms_for_user == 0:
        keyboard_sms.add(InlineKeyboardButton("Да", callback_data='my_settings_yes_needed_sms_for_user'))
    else:
        keyboard_sms.add(InlineKeyboardButton("Нет", callback_data='my_settings_no_needed_sms_for_user'))

    await bot.send_message(user_id, text, reply_markup=keyboard_sms)

    text = '➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'

    if notification_preferences == 0:
        text += 'На данный момент вы не подписаны на рассылку.\n'
    else:
        text += 'На данный момент вы подписаны на рассылку.\n'

    text += '➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'
    text += 'Хотите ли вы подписаться на рассылку?\n'
    text += '➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'

    keyboard_notification = InlineKeyboardMarkup()
    if notification_preferences == 0:
        keyboard_notification.add(InlineKeyboardButton("Да", callback_data='my_settings_yes_notification_preferences'))
    else:
        keyboard_notification.add(InlineKeyboardButton("Нет", callback_data='my_settings_no_notification_preferences'))

    await bot.send_message(user_id, text, reply_markup=keyboard_notification)


@dp.callback_query_handler(text='check_rating')
async def check_rating(callback_query: types.CallbackQuery):
    try:
        cursor.execute('''
            SELECT author_id, SUM(votes) AS total_votes
            FROM (
                SELECT author_id, votes
                FROM KnowledgeRequests
                UNION ALL
                SELECT author_id, votes
                FROM KnowledgeResponses
            ) AS combined
            GROUP BY author_id
            ORDER BY total_votes DESC
            LIMIT 5
        ''')

        top_users = cursor.fetchall()

        if top_users:
            rating_message = "Топ-5 пользователей с наибольшим количеством голосов:\n"
            for idx, (author_id, total_votes) in enumerate(top_users, start=1):
                rating_message += f"{idx}. Пользователь ID {author_id}: {total_votes} голосов\n"
        else:
            rating_message = "Пока нет данных о рейтинге."

        await bot.send_message(callback_query.from_user.id, rating_message)

    except Exception as e:
        await bot.send_message(callback_query.from_user.id, f"Произошла ошибка: {e}")


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
                               text="Введите текст нового запроса или отправьте файл вашего запроса:")
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text=f"Произошла ошибка: {e}")


@dp.message_handler(state=EnterRequestText.waiting_for_request_text, content_types=[
    types.ContentType.TEXT,
    types.ContentType.DOCUMENT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.VOICE,
    types.ContentType.VIDEO_NOTE
])
async def process_request_text(message: types.Message, state: FSMContext):
    """Обработчик для текста нового запроса или отправки файла."""
    try:
        request_text = message.text.strip() if message.text else ""  # Проверка на наличие текста запроса
        async with state.proxy() as data:
            tag_id = data['tag_id']
        media_file_id = None
        if message.photo:
            media_file_id = message.photo[-1].file_id
        elif message.video:
            media_file_id = message.video.file_id
        elif message.voice:
            media_file_id = message.voice.file_id
        elif message.document:
            media_file_id = message.document.file_id
        cursor.execute(
            "INSERT INTO KnowledgeRequests (author_id, request_text, request_media, id_tag) VALUES (?, ?, ?, ?)",
            (message.from_user.id, request_text, media_file_id, tag_id))
        conn.commit()
        await message.answer("Запрос был отправлен на проверку!")
        await state.finish()
    except Exception as e:
        await message.answer(f"Произошла ошибка при добавлении запроса: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('view_all_requests_'))
async def view_all_requests_callback(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        tag_id = callback_query.data.split('_')[-1]
        async with state.proxy() as data:
            data['tag_id'] = tag_id
        # Получение названия тега по его ID
        cursor.execute("SELECT tag_name FROM Tags WHERE id=?", (tag_id,))
        tag_name = cursor.fetchone()[0]  # Предполагается, что запрос вернет одну запись

        cursor.execute("""
            SELECT kr.id, kr.request_text, kr.request_media,
                   (SELECT COUNT(id) FROM KnowledgeResponses WHERE request_id = kr.id) AS num_responses,
                   EXISTS(SELECT 1 FROM KnowledgeResponses WHERE request_id = kr.id) AS has_responses,
                   kr.votes
            FROM KnowledgeRequests kr
            WHERE id_tag = ? AND moderated = 1
            ORDER BY kr.votes DESC
        """, (tag_id,))
        requests = cursor.fetchall()
        if requests:
            for request in requests:
                request_id, request_text, request_media, num_responses, has_responses, votes = request
                response_text = f"{request_id}. Запрос: {request_text}\n"
                response_text += f"Количество ответов: {num_responses}\n"
                response_text += f"Голосов: {votes}\n"
                if request_media:
                    if request_media.startswith("AgAC"):
                        await bot.send_photo(chat_id=callback_query.from_user.id, photo=request_media,
                                             caption=response_text)
                    elif request_media.startswith("BAAC"):
                        await bot.send_video(chat_id=callback_query.from_user.id, video=request_media,
                                             caption=response_text)
                    elif request_media.startswith("AwAC"):
                        await bot.send_voice(chat_id=callback_query.from_user.id, voice=request_media,
                                             caption=response_text)
                    elif request_media.startswith("BQAC"):
                        await bot.send_document(chat_id=callback_query.from_user.id, document=request_media,
                                                caption=response_text)
                    elif request_media.startswith("DQAC"):
                        await bot.send_message(chat_id=message.chat.id, text=response_message)
                        await bot.send_video_note(chat_id=message.chat.id, video_note=response_media)
                else:
                    await bot.send_message(chat_id=callback_query.from_user.id, text=response_text)
        else:
            response_text = f"Для тега {tag_name} пока нет запросов."
            await bot.send_message(chat_id=callback_query.from_user.id, text=response_text,
                                   reply_markup=await keyboards.check_answers_and_create_answer(tag_id))
        if response_text != f"Для тега {tag_name} пока нет запросов.":
            await bot.send_message(chat_id=callback_query.from_user.id,
                                   text='Нажмите на кнопку ниже, что посмотреть ответы.',
                                   reply_markup=await keyboards.check_answers_and_create_answer(tag_id))
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


@dp.message_handler(state=AnswerRequest.waiting_for_request_id)
async def process_request_id(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            tag_id = data.get('tag_id')

        request_id = int(message.text)

        cursor.execute("""
            SELECT kr.id, kr.request_text, t.tag_name
            FROM KnowledgeRequests kr
            LEFT JOIN Tags t ON kr.id_tag = t.id
            WHERE kr.id_tag = ? AND kr.id = ?
        """, (tag_id, request_id))
        request_info = cursor.fetchone()

        if request_info:
            request_id, request_text, tag_name = request_info

            cursor.execute("""
                SELECT response_text, response_media, author_id, timestamp, votes, id
                FROM KnowledgeResponses
                WHERE request_id = ? AND moderated = 1
                ORDER BY votes DESC
            """, (request_id,))
            responses = cursor.fetchall()

            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("Создать ответ", callback_data=f"create_response_{request_id}"))
            keyboard.add(InlineKeyboardButton("Проголосовать за вопрос", callback_data=f"vote_question_{request_id}"))
            keyboard.add(InlineKeyboardButton("Проголосовать за ответ", callback_data=f"vote_response_{request_id}"))

            if responses:
                await bot.send_message(chat_id=message.chat.id, text=f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                                                                     f"ID Тега: {tag_id}\n"
                                                                     f"Название тега: {tag_name}\n"
                                                                     f"Запрос: {request_text}\n"
                                                                     f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                                                                     f"Ответы:\n"
                                                                     f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n")
                for idx, (temp_response_text, response_media, author_id, timestamp, votes, response_id) in enumerate(
                        responses, start=1):
                    response_message = f"Номер ответа: {response_id}.\nID Пользователя: {author_id}\nКоличество голосов: {votes}\nВремя: {timestamp}\n"
                    response_message += f"Ответ: {temp_response_text}\n"
                    if response_media:
                        if response_media.startswith("AgAC"):
                            await bot.send_photo(chat_id=message.chat.id, photo=response_media,
                                                 caption=response_message)
                        elif response_media.startswith("BAAC"):
                            await bot.send_video(chat_id=message.chat.id, video=response_media,
                                                 caption=response_message)
                        elif response_media.startswith("AwAC"):
                            await bot.send_voice(chat_id=message.chat.id, voice=response_media,
                                                 caption=response_message)
                        elif response_media.startswith("BQAC"):
                            await bot.send_document(chat_id=message.chat.id, document=response_media,
                                                    caption=response_message)
                        elif response_media.startswith("DQAC"):
                            await bot.send_message(chat_id=message.chat.id, text=response_message)
                            await bot.send_video_note(chat_id=message.chat.id, video_note=response_media)
                    else:
                        await bot.send_message(chat_id=message.chat.id, text=response_message)

                await bot.send_message(chat_id=message.chat.id, text="Что вы хотите сделать?",
                                       reply_markup=keyboard)
            else:
                await bot.send_message(chat_id=message.chat.id, text="Нет ответов на данный запрос.\n",
                                       reply_markup=keyboard)

        else:
            await bot.send_message(chat_id=message.chat.id, text="Вопрос с указанным номером не найден.")

    except ValueError:
        await bot.send_message(chat_id=message.chat.id, text="Неверный формат ввода номера вопроса.")

    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text=f"Произошла ошибка: {e}")
    finally:
        await state.finish()


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

        if requests_with_answers:
            await bot.send_message(chat_id=callback_query.from_user.id,
                                   text="Введите номер вопроса, где вы хотите посмотреть ответы:")
            await AnswerRequest.waiting_for_request_id.set()
        else:
            await bot.send_message(chat_id=callback_query.from_user.id,
                                   text="Введите номер вопроса, где вы хотите посмотреть ответы:")
            await AnswerRequest.waiting_for_request_id.set()
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


@dp.message_handler(state=AnswerResponse.waiting_for_response_text, content_types=[
    types.ContentType.TEXT,
    types.ContentType.DOCUMENT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.VOICE,
    types.ContentType.VIDEO_NOTE
])
async def create_response(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            request_id = data['request_id']

        response_text = message.text if message.text else "Нет ответа в виде текста."
        author_id = message.from_user.id

        file_id = None

        if message.document:
            file_id = message.document.file_id
            await message.document.download(destination_dir='responses_documents')
        elif message.photo:
            file_id = message.photo[-1].file_id
            await message.photo[-1].download(destination_dir='responses_photos')
        elif message.video:
            file_id = message.video.file_id
            await message.video.download(destination_dir='responses_videos')
        elif message.voice:
            file_id = message.voice.file_id
            await message.voice.download(destination_dir='responses_voice_messages')
        elif message.video_note:
            file_id = message.video_note.file_id
            await message.video_note.download(destination_dir='responses_video_notes')

        cursor.execute("""
            INSERT INTO KnowledgeResponses (request_id, author_id, response_text, response_media)
            VALUES (?, ?, ?, ?)
        """, (request_id, author_id, response_text, file_id))
        conn.commit()

        await bot.send_message(chat_id=message.chat.id, text="Ваш ответ сохранен и отправлен на модерацию")

        cursor.execute("""
            SELECT kr.author_id, kr.request_text, t.tag_name, kr.request_media
            FROM KnowledgeRequests kr
            LEFT JOIN Tags t ON kr.id_tag = t.id
            WHERE kr.id = ?
        """, (request_id,))
        request_info = cursor.fetchone()

        request_author_id, request_text, tag_name, request_media = request_info

        cursor.execute("SELECT notification_preferences FROM Users WHERE id = ?", (request_author_id,))
        subscription_status = cursor.fetchone()

        if subscription_status and subscription_status[0] == 1:
            notification_message = (f"Пользователь {message.from_user.id} ответил на ваш запрос!\n\n"
                                    f"Ваш запрос: '{request_text}'\nНазвание тега: {tag_name}\n"
                                    f"ID Пользователя: {message.from_user.id}\n"
                                    f"Его ответ: {response_text}")
            if request_media:
                if request_media.startswith("AgAC"):
                    await bot.send_photo(request_author_id, request_media, caption=notification_message)
                elif request_media.startswith("BAAC"):
                    await bot.send_video(request_author_id, request_media, caption=notification_message)
                elif request_media.startswith("AwAC"):
                    await bot.send_voice(request_author_id, request_media, caption=notification_message)
                elif request_media.startswith("AQAC"):
                    await bot.send_document(request_author_id, request_media, caption=notification_message)
                elif request_media.startswith("DQAC"):
                    await bot.send_message(chat_id=message.chat.id, text=response_message)
                    await bot.send_video_note(chat_id=message.chat.id, video_note=response_media)

            if file_id:
                if file_id.startswith("AgAC"):
                    await bot.send_photo(request_author_id, file_id)
                elif file_id.startswith("BAAC"):
                    await bot.send_video(request_author_id, file_id)
                elif file_id.startswith("AwAC"):
                    await bot.send_voice(request_author_id, file_id)
                elif file_id.startswith("BQAC"):
                    await bot.send_document(request_author_id, file_id)
                elif file_id.startswith("DQAC"):
                    await bot.send_video_note(request_author_id, file_id)
            else:
                await bot.send_message(request_author_id, notification_message)

        await state.finish()

    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text=f"Произошла ошибка: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('vote_question_'))
async def vote_question(callback_query: types.CallbackQuery):
    try:
        request_id = int(callback_query.data.split('_')[-1])
        user_id = callback_query.from_user.id

        cursor.execute("SELECT 1 FROM QuestionVotes WHERE user_id = ? AND question_id = ?", (user_id, request_id))
        existing_vote = cursor.fetchone()

        if existing_vote:
            await bot.answer_callback_query(callback_query.id, text="Вы уже голосовали за этот вопрос!")
        else:
            cursor.execute("UPDATE KnowledgeRequests SET votes = votes + 1 WHERE id = ?", (request_id,))
            cursor.execute("INSERT INTO QuestionVotes (user_id, question_id) VALUES (?, ?)", (user_id, request_id))
            conn.commit()

            await bot.answer_callback_query(callback_query.id, text="Вы успешно проголосовали за вопрос!")

    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('vote_response_'))
async def vote_response(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text="Введите номер ответа, за который хотите проголосовать:")

        await AnswerRequest.waiting_for_response_id.set()

        async with state.proxy() as data:
            data['response_id'] = int(callback_query.data.split('_')[-1])
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


@dp.message_handler(state=AnswerRequest.waiting_for_response_id)
async def process_response_id(message: types.Message, state: FSMContext):
    try:
        response_id = int(message.text)

        async with state.proxy() as data:
            response_id = data['response_id']

        user_id = message.from_user.id

        cursor.execute("SELECT 1 FROM ResponseVotes WHERE user_id = ? AND response_id = ?", (user_id, response_id))
        existing_vote = cursor.fetchone()

        if existing_vote:
            await message.answer("Вы уже голосовали за этот ответ!")
        else:
            cursor.execute("""
                UPDATE KnowledgeResponses
                SET votes = votes + 1
                WHERE id = ?
            """, (response_id,))
            conn.commit()

            cursor.execute("INSERT INTO ResponseVotes (user_id, response_id) VALUES (?, ?)", (user_id, response_id))
            conn.commit()

            await message.answer("Ваш голос за ответ успешно засчитан!")

            await state.finish()

    except ValueError:
        await message.answer("Неверный формат ввода номера ответа.")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")


if __name__ == '__main__':
    dp.register_message_handler(handler_start, commands=['start'], state='*')
    register.all_callback(dp)
    executor.start_polling(dp, skip_updates=True)
