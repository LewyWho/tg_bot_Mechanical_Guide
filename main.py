import asyncio
import os
import sqlite3
import time
from aiogram.utils.exceptions import BadRequest
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
    await dp.bot.set_my_commands([
        types.BotCommand("start", "♻️ Главное меню"),
        types.BotCommand("help", "❓ Помощь"),
        types.BotCommand("login", "🔑 Войти как администратор")
    ])
    await state.finish()
    check_ban = cursor.execute("SELECT banned FROM Users WHERE id =?", (message.from_user.id,)).fetchone()
    verify = cursor.execute('SELECT * FROM Users WHERE id =?', (message.from_user.id,)).fetchone()
    if not verify:
        await bot.send_message(chat_id=message.from_user.id,
                               text=sms.message_start())
        await bot.send_message(chat_id=message.from_user.id, text=sms.register_start())

        await bot.send_message(chat_id=message.from_user.id, text=sms.need_notification_or_not(),
                               reply_markup=await keyboards.need_notification_or_not())
    else:
        if check_ban[0] == 1:
            await message.answer("❌ Вы не можете использовать эту команду, так как вы заблокированы.")
        else:
            await bot.send_message(chat_id=message.from_user.id, text=sms.profile_user(message.from_user.id),
                                   reply_markup=await keyboards.main_menu())


@dp.message_handler(commands=['delete_user'], state='*')
async def delete_user(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    cursor.execute("SELECT role FROM Users WHERE id=?", (user_id,))
    user_role = cursor.fetchone()

    if not user_role or user_role[0] != 1:
        await message.answer("❌ Вы не являетесь администратором и не имеете доступа к этой команде.")
        return

    args = message.get_args()

    if not args:
        await message.answer(
            "❌ Вы не указали ID пользователя для удаления. \nИспользуйте команду /delete_user <b>ID пользователя</b>.")
        return

    try:
        user_id_to_delete = int(args)
    except ValueError:
        await message.answer("❌ Некорректный формат ID пользователя. Пожалуйста, введите целочисленное значение.")
        return

    cursor.execute("SELECT username FROM Users WHERE id=?", (user_id_to_delete,))
    user_to_delete = cursor.fetchone()

    if not user_to_delete:
        await message.answer("❌ Пользователя с указанным ID не существует.")
        return

    cursor.execute("DELETE FROM Users WHERE id=?", (user_id_to_delete,))
    conn.commit()

    await message.answer(f"✅ Пользователь с ID {user_id_to_delete} успешно удален.")


@dp.message_handler(commands=['ban_user'], state='*')
async def handler_ban_user(message: types.Message, state: FSMContext):
    args = message.get_args()
    if not args:
        await message.answer("❌ Вы не указали ID пользователя. Используйте команду /ban_user <b>ID пользователя</b>.")
        return

    user_id = args

    cursor.execute("UPDATE Users SET banned = 1 WHERE id=?", (user_id,))
    conn.commit()

    await message.answer(f"✅ Пользователь с ID {user_id} заблокирован.")


@dp.message_handler(commands=['check_answers'], state='*', content_types=[
    types.ContentType.TEXT,
    types.ContentType.DOCUMENT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.VOICE,
    types.ContentType.VIDEO_NOTE
])
async def handler_check_answers(message: types.Message, state: FSMContext):
    admins = cursor.execute("SELECT user_id FROM Admins WHERE user_id =?", (message.from_user.id,)).fetchone()
    if not admins:
        await bot.send_message(chat_id=message.from_user.id, text="❌ У вас нет доступа к этой команде.")
        return
    else:
        cursor.execute("""
            SELECT kr.id, kr.response_text, kr.response_media, kr.author_id, u.username
            FROM KnowledgeResponses kr
            JOIN Users u ON kr.author_id = u.id
            WHERE kr.moderated = 0
        """)
        unmoderated_answers = cursor.fetchall()

        if not unmoderated_answers:
            await message.answer("Нет немодерированных ответов.")
            return

        for answer_id, response_text, response_media, author_id, username in unmoderated_answers:
            answer_message = f"🆔 ID ответа: {answer_id}\n" \
                             f"👤 Автор: @{username} (ID: {author_id})\n" \
                             f"💬 Ответ: {response_text}\n"
            if response_media:
                if response_media.startswith("AgAC"):
                    await bot.send_photo(chat_id=message.chat.id, photo=response_media, caption=answer_message)
                elif response_media.startswith("BAAC"):
                    await bot.send_video(chat_id=message.chat.id, video=response_media, caption=answer_message)
                elif response_media.startswith("AwAC"):
                    await bot.send_voice(chat_id=message.chat.id, voice=response_media, caption=answer_message)
                elif response_media.startswith("BQAC"):
                    await bot.send_document(chat_id=message.chat.id, document=response_media, caption=answer_message)
                elif response_media.startswith("DQAC"):
                    await bot.send_message(chat_id=message.chat.id, text=answer_message)
                    await bot.send_video_note(chat_id=message.chat.id, video_note=response_media)
            else:
                await message.answer(answer_message)

        await message.answer("Выберите ID ответа для модерации, используя команду /approve_answer <b>ID</b> или "
                             "/reject_answer <b>ID</b>.")


@dp.message_handler(commands=['approve_question'])
async def approve_question(message: types.Message):
    admins = cursor.execute("SELECT user_id FROM Admins WHERE user_id =?", (message.from_user.id,)).fetchone()
    if not admins:
        await bot.send_message(chat_id=message.from_user.id, text="❌ У вас нет доступа к этой команде.")
    else:
        question_id = message.get_args()
        if not question_id.isdigit():
            await message.answer("❌ Некорректный формат ID вопроса. Пожалуйста, укажите числовое значение ID.")
            return
        await message.answer(f"✅ Вопрос с ID {question_id} был принят.")

        cursor.execute("UPDATE KnowledgeRequests SET moderated = 1 WHERE id = ?", (question_id,))
        conn.commit()

        cursor.execute("""
            SELECT rq.author_id, u.username
            FROM KnowledgeRequests rq
            JOIN Users u ON rq.author_id = u.id
            WHERE rq.id = ?
        """, (question_id,))
        result = cursor.fetchone()

        if result:
            author_id, username = result

            media_file = \
                cursor.execute("SELECT request_media FROM KnowledgeRequests WHERE id = ?", (question_id,)).fetchone()[0]

            caption = f"✅ Ваш вопрос с ID {question_id} был принят модератором.\nВаш запрос находится в прикрепленном файле."

            if media_file:
                if media_file.startswith("AgAC"):
                    await bot.send_photo(author_id, photo=media_file, caption=caption)
                elif media_file.startswith("BAAC"):
                    await bot.send_video(author_id, video=media_file, caption=caption)
                elif media_file.startswith("AwAC"):
                    await bot.send_voice(author_id, voice=media_file, caption=caption)
                elif media_file.startswith("BQAC"):
                    await bot.send_document(author_id, document=media_file, caption=caption)
                elif media_file.startswith("DQAC"):
                    await bot.send_message(author_id, caption)
                    await bot.send_video_note(author_id, video_note=media_file, )
            else:
                response_text = \
                    cursor.execute("SELECT request_text FROM KnowledgeRequests WHERE id =?", (question_id,)).fetchone()[0]
                await bot.send_message(author_id,
                                       f"✅ Ваш вопрос с ID {question_id} был принят модератором.\nВаш запрос: {response_text}.")
        else:
            await message.answer("❌ Не удалось найти информацию о пользователе, отправившем вопрос.")


@dp.message_handler(commands=['reject_question'])
async def reject_question(message: types.Message):
    admins = cursor.execute("SELECT user_id FROM Admins WHERE user_id =?", (message.from_user.id,)).fetchone()
    if not admins:
        await bot.send_message(chat_id=message.from_user.id, text="❌ У вас нет доступа к этой команде.")
    else:
        question_id = message.get_args()
        if not question_id.isdigit():
            await message.answer("❌ Некорректный формат ID вопроса. Пожалуйста, укажите числовое значение ID.")
            return
        await message.answer(f"✅ Вопрос с ID {question_id} был отклонен.")

        cursor.execute("DELETE FROM KnowledgeRequests WHERE id = ?", (question_id,))
        conn.commit()

        cursor.execute("""
            SELECT author_id
            FROM KnowledgeRequests
            WHERE id = ?
        """, (question_id,))
        result = cursor.fetchone()

        if result:
            author_id = result[0]
            await bot.send_message(author_id, f"❌ Ваш вопрос с ID {question_id} был отклонен модератором.")
        else:
            await message.answer("❌ Не удалось найти информацию о пользователе, отправившем вопрос.")


@dp.message_handler(commands=['approve_answer'], content_types=[
    types.ContentType.TEXT,
    types.ContentType.DOCUMENT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.VOICE,
    types.ContentType.VIDEO_NOTE
])
async def approve_answer(message: types.Message, state: FSMContext):
    admins = cursor.execute("SELECT user_id FROM Admins WHERE user_id =?", (message.from_user.id,)).fetchone()
    if not admins:
        await bot.send_message(chat_id=message.from_user.id, text="❌ У вас нет доступа к этой команде.")
    else:
        answer_id = message.get_args()
        if not answer_id.isdigit():
            await message.answer("❌ Некорректный формат ID ответа. Пожалуйста, укажите числовое значение ID.")
            return

        cursor.execute("UPDATE KnowledgeResponses SET moderated = 1 WHERE id = ?", (answer_id,))
        conn.commit()

        cursor.execute("""
            SELECT kr.author_id, kr.request_id, kr.response_text, kr.response_media,
                   rq.author_id AS request_author_id, rq.request_text, t.tag_name, u.username
            FROM KnowledgeResponses kr
            JOIN KnowledgeRequests rq ON kr.request_id = rq.id
            LEFT JOIN Tags t ON rq.id_tag = t.id
            JOIN Users u ON kr.author_id = u.id
            WHERE kr.id = ?
        """, (answer_id,))
        result = cursor.fetchone()

        if result:
            author_id, request_id, response_text, response_media, request_author_id, request_text, tag_name, author_username = result

            if response_media:
                if response_media.startswith("AgAC"):
                    await bot.send_photo(author_id, response_media,
                                         caption=f"✅ Ваш ответ к тегу {tag_name} был принят.\nВаш ответ прикреплен к сообщению.")

                    await bot.send_photo(request_author_id, response_media,
                                         caption=f"🔍 Ваш запрос: '{request_text}'\n🏷️ Название тега: {tag_name}\n" \
                                                 f"🆔 ID Пользователя: <code>{author_id}</code>\n\n" \
                                                 f"👤 Имя пользователя: @{author_username}\n" \
                                                 f"💬 Его ответ: {response_text}")
                elif response_media.startswith("BAAC"):
                    await bot.send_video(author_id, response_media,
                                         caption=f"✅ Ваш ответ к тегу {tag_name} был принят.\nВаш ответ прикреплен к сообщению.")

                    await bot.send_video(request_author_id, response_media,
                                         caption=f"🔍 Ваш запрос: '{request_text}'\n🏷️ Название тега: {tag_name}\n" \
                                                 f"🆔 ID Пользователя: <code>{author_id}</code>\n\n" \
                                                 f"👤 Имя пользователя: @{author_username}\n" \
                                                 f"💬 Его ответ: {response_text}")
                elif response_media.startswith("AwAC"):
                    try:
                        await bot.send_voice(author_id, response_media,
                                             caption=f"✅ Ваш ответ к тегу {tag_name} был принят.\nВаш ответ прикреплен к сообщению.")
                    except BadRequest as e:
                        await bot.send_message(author_id, text=f"✅ Ваш ответ к тегу {tag_name} был принят.")
                    try:
                        await bot.send_voice(request_author_id, response_media,
                                             caption=f"🔍 Ваш запрос: '{request_text}'\n🏷️ Название тега: {tag_name}\n" \
                                                     f"🆔 ID Пользователя: <code>{author_id}</code>\n\n" \
                                                     f"👤 Имя пользователя: @{author_username}\n" \
                                                     f"💬 Его ответ: {response_text}")
                    except BadRequest as e:
                        await bot.send_message(request_author_id,
                                               text=f"🔍 Ваш запрос: '{request_text}'\n🏷️ Название тега: {tag_name}\n" \
                                                    f"🆔 ID Пользователя: <code>{author_id}</code>\n\n" \
                                                    f"👤 Имя пользователя: @{author_username}\n" \
                                                    f"💬 Его ответ: {response_text}")
                elif response_media.startswith("BQAC"):
                    await bot.send_document(author_id, response_media,
                                            caption=f"✅ Ваш ответ к тегу {tag_name} был принят.\nВаш ответ прикреплен к сообщению.")

                    await bot.send_document(request_author_id, response_media,
                                            caption=f"🔍 Ваш запрос: '{request_text}'\n🏷️ Название тега: {tag_name}\n" \
                                                    f"🆔 ID Пользователя: <code>{author_id}</code>\n\n" \
                                                    f"👤 Имя пользователя: @{author_username}\n" \
                                                    f"💬 Его ответ: {response_text}")
                elif response_media.startswith("DQAC"):
                    try:
                        await bot.send_message(author_id, f"✅ Ваш ответ к тегу {tag_name} был принят.\nВаш ответ: ")
                        await bot.send_video_note(author_id, response_media)
                    except BadRequest as e:
                        await bot.send_message(author_id, text=f"✅ Ваш ответ к тегу {tag_name} был принят.")

                    try:
                        await bot.send_message(request_author_id,
                                               text=f"🔍 Ваш запрос: '{request_text}'\n🏷️ Название тега: {tag_name}\n" \
                                                    f"🆔 ID Пользователя: <code>{author_id}</code>\n\n" \
                                                    f"👤 Имя пользователя: @{author_username}\n" \
                                                    f"💬 Его ответ: {response_text}")
                        await bot.send_video_note(request_author_id, response_media)
                    except BadRequest as e:
                        await bot.send_message(request_author_id,
                                               text=f"🔍 Ваш запрос: '{request_text}'\n🏷️ Название тега: {tag_name}\n" \
                                                    f"🆔 ID Пользователя: <code>{author_id}</code>\n\n" \
                                                    f"👤 Имя пользователя: @{author_username}\n" \
                                                    f"💬 Его ответ: {response_text}")
            else:
                await bot.send_message(author_id, f"✅ Ваш ответ к тегу {tag_name} был принят.\nВаш ответ: {response_text}")

                await bot.send_message(request_author_id,
                                       text=f"🔍 Ваш запрос: '{request_text}'\n🏷️ Название тега: {tag_name}\n" \
                                            f"🆔 ID Пользователя: <code>{author_id}</code>\n\n" \
                                            f"👤 Имя пользователя: @{author_username}\n" \
                                            f"💬 Его ответ: {response_text}")

            await message.answer("✅ Ответ успешно принят и отправлен автору запроса.")
        else:
            await message.answer("❌ Не удалось найти информацию об ответе.")


@dp.message_handler(commands=['reject_answer'])
async def reject_answer(message: types.Message):
    admins = cursor.execute("SELECT user_id FROM Admins WHERE user_id =?", (message.from_user.id,)).fetchone()
    if not admins:
        await bot.send_message(chat_id=message.from_user.id, text="❌ У вас нет доступа к этой команде.")
    else:
        answer_id = message.get_args()
        if not answer_id.isdigit():
            await message.answer("❌ Некорректный формат ID ответа. Пожалуйста, укажите числовое значение ID.")
            return

        cursor.execute("""
            SELECT author_id
            FROM KnowledgeResponses
            WHERE id = ?
        """, (answer_id,))
        result = cursor.fetchone()

        if result:
            author_id = result[0]
            await bot.send_message(author_id, f"❌ Ваш ответ с ID {answer_id} был отклонен модератором.")
            await message.answer("✅ Ответ успешно отклонен.")

            cursor.execute("DELETE FROM KnowledgeResponses WHERE id = ?", (answer_id,))
            conn.commit()
        else:
            await message.answer("❌ Не удалось найти информацию об ответе.")


@dp.message_handler(commands=['check_questions'], state='*', content_types=[
    types.ContentType.TEXT,
    types.ContentType.DOCUMENT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.VOICE,
    types.ContentType.VIDEO_NOTE
])
async def handler_check_questions(message: types.Message, state: FSMContext):
    admins = cursor.execute("SELECT user_id FROM Admins WHERE user_id =?", (message.from_user.id,)).fetchone()
    if not admins:
        await bot.send_message(chat_id=message.from_user.id, text="❌ У вас нет доступа к этой команде.")
    else:
        cursor.execute("""
            SELECT rq.id, rq.request_text, rq.request_media, rq.author_id, u.username
            FROM KnowledgeRequests rq
            JOIN Users u ON rq.author_id = u.id
            LEFT JOIN KnowledgeResponses kr ON rq.id = kr.request_id
            WHERE rq.moderated = 0
        """)
        unmoderated_questions = cursor.fetchall()

        if not unmoderated_questions:
            await message.answer("Нет немодерированных вопросов.")
            return

        for question_id, request_text, request_media, author_id, username in unmoderated_questions:
            question_message = f"🆔 ID вопроса: {question_id}\n" \
                               f"👤 Автор: @{username} (ID: <code>{author_id}</code>)\n" \
                               f"💬 Вопрос: {request_text}\n"
            if request_media:
                if request_media.startswith("AgAC"):
                    await bot.send_photo(chat_id=message.chat.id, photo=request_media, caption=question_message)
                elif request_media.startswith("BAAC"):
                    await bot.send_video(chat_id=message.chat.id, video=request_media, caption=question_message)
                elif request_media.startswith("AwAC"):
                    await bot.send_voice(chat_id=message.chat.id, voice=request_media, caption=question_message)
                elif request_media.startswith("BQAC"):
                    await bot.send_document(chat_id=message.chat.id, document=request_media, caption=question_message)
                elif request_media.startswith("DQAC"):
                    await bot.send_message(chat_id=message.chat.id, text=question_message)
                    await bot.send_video_note(chat_id=message.chat.id, video_note=request_media)
            else:
                await message.answer(question_message)

        await message.answer("Выберите ID вопроса для модерации, используя команду /approve_question <b>ID</b> или "
                             "/reject_question <b>ID</b>.")


@dp.message_handler(commands=['mailing'], state='*')
async def handler_mailing(message: types.Message, state: FSMContext):
    admins = cursor.execute("SELECT user_id FROM Admins WHERE user_id =?", (message.from_user.id,)).fetchone()
    if not admins:
        await bot.send_message(chat_id=message.from_user.id, text="❌ У вас нет доступа к этой команде.")
    else:
        args = message.get_args()
        if not args:
            await message.answer("❌ Вы не указали текст сообщения. Используйте команду /mailing <текст сообщения>.")
            return

        sms_text = args

        sms_text = f"💬 Рассылка: {sms_text}"

        cursor.execute("SELECT id FROM Users")
        user_ids = cursor.fetchall()

        for user_id in user_ids:
            try:
                await bot.send_message(chat_id=user_id[0], text=sms_text)
            except Exception as e:
                print(f"Ошибка при отправке сообщения пользователю с ID {user_id[0]}: {e}")

        await message.answer("✅ Рассылка завершена.")


@dp.message_handler(commands=['unban_user'], state='*')
async def handler_unban_user(message: types.Message, state: FSMContext):
    admins = cursor.execute("SELECT user_id FROM Admins WHERE user_id =?", (message.from_user.id,)).fetchone()
    if not admins:
        await bot.send_message(chat_id=message.from_user.id, text="❌ У вас нет доступа к этой команде.")
    else:
        args = message.get_args()
        if not args:
            await message.answer("❌ Вы не указали ID пользователя. Используйте команду /unban_user <b>ID пользователя</b>.")
            return

        user_id = args

        cursor.execute("UPDATE Users SET banned = 0 WHERE id=?", (user_id,))
        conn.commit()

        await message.answer(f"✅ Пользователь с ID {user_id} разблокирован.")


@dp.message_handler(commands=['sms_user'], state='*')
async def handler_sms_user(message: types.Message, state: FSMContext):
    admins = cursor.execute("SELECT user_id FROM Admins WHERE user_id =?", (message.from_user.id,)).fetchone()
    if not admins:
        await bot.send_message(chat_id=message.from_user.id, text="❌ У вас нет доступа к этой команде.")
    else:
        args = message.get_args()
        if not args:
            await message.answer("❌ Вы не указали ID пользователя и текст сообщения.\n"
                                 "Используйте команду /sms_user <b>ID пользователя</b> <b>текст сообщения</b>.")
            return

        try:
            user_id, sms_text = args.split(maxsplit=1)
        except ValueError:
            await message.answer(
                "❌ Некорректный формат. Используйте команду /sms_user <b>ID пользователя</b> <b>текст сообщения</b>.")
            return

        cursor.execute("SELECT username FROM Users WHERE id=?", (user_id,))
        username = cursor.fetchone()
        if username:
            username = username[0]
        else:
            username = "неизвестно"

        sms_text = f"💬 Сообщение от администратора:\n{sms_text}"

        await bot.send_message(chat_id=user_id, text=sms_text)
        await message.answer(f"✅ Сообщение отправлено пользователю с ID {user_id} ({username}).")


@dp.message_handler(commands=['login'], state='*')
async def handler_login_admin(message: types.Message, state: FSMContext):
    args = message.get_args()
    if not args:
        await message.answer("❌ Вы не указали пароль. Используйте команду /login <b>пароль</b>.")
        return

    user_id = message.from_user.id

    cursor.execute("SELECT password FROM Admins WHERE user_id=?", (user_id,))
    admin_password = cursor.fetchone()

    if not admin_password:
        await message.answer("❌ У вас нет прав администратора.")
        return

    if args == admin_password[0]:
        await message.answer("✅ Вы успешно вошли в систему как администратор.")
        cursor.execute("UPDATE Users SET role = 1 WHERE id =?", (user_id,))
        conn.commit()
    else:
        await message.answer("❌ Неверный пароль. Попробуйте еще раз.")


@dp.message_handler(commands=['admin_help'], state='*')
async def handler_admin_help(message: types.Message, state: FSMContext):
    admins = cursor.execute("SELECT user_id FROM Admins WHERE user_id =?", (message.from_user.id,)).fetchone()
    if not admins:
        await bot.send_message(chat_id=message.from_user.id, text="❌ У вас нет доступа к этой команде.")
    else:
        admin = cursor.execute('SELECT * FROM Admins WHERE user_id =?', (message.from_user.id,)).fetchone()[0]
        if admin:
            await bot.send_message(chat_id=message.from_user.id, text=sms.admin_help())


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
            users_message += f"🆔 ID: {user_id}\n" \
                             f"👤 Имя пользователя: {username}\n" \
                             f"🏅 Ранг: {rank_user}\n" \
                             f"💡 Запросов на знания: {total_requests}\n" \
                             f"💬 Ответов: {total_responses}\n" \
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
    await message.answer("✅ Операция отменена.")


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
        await message.answer("❌ У вас нет ни одного ответа для изменения.")
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
        await message.answer("❌ Пожалуйста, введите корректный номер вопроса.")
        return

    async with state.proxy() as data:
        data['question_number'] = question_number

    await message.answer("Введите ваш новый ответ:")

    await ChangeAnswer.waiting_for_new_answer.set()


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
            await message.answer("❌ Вы не ввели новый ответ.")
            return

    cursor.execute(
        "UPDATE KnowledgeResponses SET response_text=?, response_media=?, moderated=0 WHERE id=? AND author_id=?",
        (new_answer, media_file_id, question_number, user_id))
    conn.commit()

    await message.answer("✅ Ответ успешно изменен и отправлен на проверку.")

    all_admins = cursor.execute("SELECT user_id FROM Admins").fetchall()
    for admin in all_admins:
        await bot.send_message(chat_id=admin[0], text=f"📩 Новый ответ от пользователя {message.from_user.id}.\n\n"
                                                      f"💭 Запрос: {new_answer}\n\n"
                                                      f"📖 Ответ: {new_answer}\n\n"
                                                      f"🆔 ID: {question_number}")

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
        await message.answer("❌ У вас нет ни одного вопроса для изменения.")
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
        await message.answer("❌ Пожалуйста, введите корректный номер вопроса.")
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
        await message.answer("❌ Вы не ввели новый вопрос или не прикрепили медиафайл.")
        return

    async with state.proxy() as data:
        user_id = message.from_user.id
        question_number = data['question_number']

    cursor.execute(
        "UPDATE KnowledgeRequests SET request_text=?, request_media=?, moderated=0 WHERE id=? AND author_id=?",
        (new_question, media_file_id, question_number, user_id))
    conn.commit()
    await message.answer("✅ Вопрос успешно изменен и отправлен на проверку.")

    admins = cursor.execute("SELECT user_id FROM Admins").fetchall()
    for admin in admins:
        await bot.send_message(chat_id=admin[0], text=f"📩 Вопрос {question_number} изменен пользователем {user_id}.")
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
            await message.reply("❌ Неверный формат команды. Используйте /sms {user_id|username} {текст}")
            return

        receiver = command_args[0]
        text = ' '.join(command_args[1:])

        # Проверяем, является ли receiver числом (user_id)
        if receiver.isdigit():
            receiver_id = int(receiver)
            user = await bot.get_chat(receiver_id)
        else:
            # Иначе ищем пользователя по username
            user = await bot.get_chat(receiver)

        if user:
            verify_try = cursor.execute("SELECT needed_sms_for_user FROM Users WHERE id =?", (user.id,)).fetchone()[0]

            if verify_try == 1:
                await bot.send_message(user.id,
                                       f"📩 Сообщение от пользователя.\n🆔 ID пользователя: <code>{from_user_id}</code>\nТекст: {text}")
                await message.reply("✅ Сообщение успешно отправлено.")
            else:
                await message.reply("❌ Пользователь отключил функцию получения сообщений.")
        else:
            await message.reply("❌ Пользователь не найден.")

    except Exception as e:
        await message.reply(f"❌ Произошла ошибка: {e}")


@dp.message_handler(commands=['my_settings'], state='*')
async def my_settings(message: types.Message):
    user_id = message.from_user.id

    cursor.execute("SELECT needed_sms_for_user, notification_preferences FROM Users WHERE id=?", (user_id,))
    settings = cursor.fetchone()

    needed_sms_for_user, notification_preferences = settings

    text = "➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
    if needed_sms_for_user == 0:
        text += "❌ На данный момент вы не хотите получать сообщения от пользователей.\n"
    else:
        text += "✅ На данный момент вы получаете сообщения от пользователей.\n"
    text += "➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
    text += "❓ Хотите ли вы получать сообщения от пользователей?\n"
    text += '➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'

    keyboard_sms = InlineKeyboardMarkup()
    if needed_sms_for_user == 0:
        keyboard_sms.add(InlineKeyboardButton("Да", callback_data='my_settings_yes_needed_sms_for_user'))
    else:
        keyboard_sms.add(InlineKeyboardButton("Нет", callback_data='my_settings_no_needed_sms_for_user'))

    await bot.send_message(user_id, text, reply_markup=keyboard_sms)

    text = '➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'

    if notification_preferences == 0:
        text += '❌ На данный момент вы не подписаны на рассылку.\n'
    else:
        text += '✅ На данный момент вы подписаны на рассылку.\n'

    text += '➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'
    text += '❓ Хотите ли вы подписаться на рассылку?\n'
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
                rating_message += f"{idx} место.\n🆔 Пользователь ID {author_id}\n🗳 Всего {total_votes} голосов\n⭐️ Звание: {cursor.execute('SELECT rank_user FROM Users WHERE id =?', (author_id,)).fetchone()[0]}\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        else:
            rating_message = "❌ Пока нет данных о рейтинге."

        await bot.send_message(callback_query.from_user.id, rating_message)

    except Exception as e:
        await bot.send_message(callback_query.from_user.id, f"❌ Произошла ошибка: {e}")


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
                               text=f"❌ Произошла ошибка: {e}")


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
                response_text += f"🔍 Запрос: {request_text}\n"
                response_text += f"🔢 Номер запроса: {idx}\n"
                if request_media:
                    if request_media.startswith("AgAC"):
                        await bot.send_photo(chat_id=user_id, photo=request_media)
                    elif request_media.startswith("BAAC"):
                        await bot.send_video(chat_id=user_id, video=request_media)
                    elif request_media.startswith("AwAC"):
                        await bot.send_voice(chat_id=user_id, voice=request_media)
                    elif request_media.startswith("BQAC"):
                        await bot.send_document(chat_id=user_id, document=request_media)
                    elif request_media.startswith("DQAC"):
                        await bot.send_video_note(chat_id=user_id, video_note=request_media)
                response_text += f"👍 Голоса: {votes}\n"
                response_text += f"🕒 Время создания: {timestamp}\n"
                response_text += f"🛡 Модерировано: {'Да' if moderated else 'Нет'}\n\n"
        else:
            response_text = "❌ У вас пока нет запросов по данному тегу."

        if user_requests and any(request[2] != 0 for request in user_requests):
            await bot.send_message(chat_id=user_id, text=response_text, reply_markup=await keyboards.check_my_answer())
        else:
            await bot.send_message(chat_id=user_id, text=response_text)

    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text=f"❌ Произошла ошибка: {e}")


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
                               text=f"❌ Произошла ошибка: {e}")


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
        request_text = message.text.strip() if message.text else ""
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
        elif message.video_note:
            media_file_id = message.video_note.file_id

        cursor.execute(
            "INSERT INTO KnowledgeRequests (author_id, request_text, request_media, id_tag) VALUES (?, ?, ?, ?)",
            (message.from_user.id, request_text, media_file_id, tag_id))
        conn.commit()

        text_tag = cursor.execute("SELECT tag_name FROM Tags WHERE id =?", (tag_id,)).fetchone()[0]

        request_id = cursor.execute("SELECT id FROM KnowledgeRequests WHERE author_id =? AND id_tag =?",
                                    (message.from_user.id, tag_id)).fetchone()[0]

        await message.answer("✅ Запрос был отправлен на проверку!")

        admins = cursor.execute("SELECT user_id FROM Admins").fetchall()
        for admin in admins:
            if media_file_id:
                if media_file_id.startswith("AgAC"):
                    await bot.send_photo(chat_id=admin[0], photo=media_file_id,
                                         caption=f"📖 Новый запрос для тега {text_tag}: {request_text}\n<code>/approve_question {request_id}</code> или <code>/reject_question {request_id}</code>")
                elif media_file_id.startswith("BAAC"):
                    await bot.send_video(chat_id=admin[0], video=media_file_id,
                                         caption=f"📖📖 Новый запрос для тега {text_tag}: {request_text}\n<code>/approve_question {request_id}</code> или <code>/reject_question {request_id}</code>")
                elif media_file_id.startswith("AwAC"):
                    await bot.send_voice(chat_id=admin[0], voice=media_file_id,
                                         caption=f"📖 Новый запрос для тега {text_tag}: {request_text}\n<code>/approve_question {request_id}</code> или <code>/reject_question {request_id}</code>")
                elif media_file_id.startswith("BQAC"):
                    await bot.send_document(chat_id=admin[0], document=media_file_id,
                                            caption=f"📖 Новый запрос для тега {text_tag}: {request_text}\n<code>/approve_question {request_id}</code> или <code>/reject_question {request_id}</code>")
                elif media_file_id.startswith("DQAC"):
                    await bot.send_video_note(chat_id=admin[0], video_note=media_file_id)
                    await bot.send_message(chat_id=admin[0],
                                           text=f"📖 Новый запрос для тега {text_tag}: {request_text}\n<code>/approve_question {request_id}</code> или <code>/reject_question {request_id}</code>")
            else:
                await bot.send_message(chat_id=admin[0],
                                       text=f"📖 Новый запрос для тега {text_tag}: {request_text}\n<code>/approve_question {request_id}</code> или <code>/reject_question {request_id}</code>")

        await state.finish()

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при добавлении запроса: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('view_all_requests_'))
async def view_all_requests_callback(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        tag_id = callback_query.data.split('_')[-1]
        async with state.proxy() as data:
            data['tag_id'] = tag_id
        cursor.execute("SELECT tag_name FROM Tags WHERE id=?", (tag_id,))
        tag_name = cursor.fetchone()[0]

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
        response_text = ""
        if requests:
            for request in requests:
                request_id, request_text, request_media, num_responses, has_responses, votes = request
                response_text = f"🆔 {request_id}. Запрос: {request_text}\n"
                response_text += f"💬 Количество ответов: {num_responses}\n"
                response_text += f"👍 Голосов: {votes}\n"
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
                        await bot.send_message(chat_id=callback_query.from_user.id, text=response_text)
                        await bot.send_video_note(chat_id=callback_query.from_user.id, video_note=request_media)
                else:
                    await bot.send_message(chat_id=callback_query.from_user.id, text=response_text)
        else:
            kb = InlineKeyboardMarkup()
            create_request_button = InlineKeyboardButton(text="Создать запрос",
                                                         callback_data=f"create_request_{tag_id}")
            kb.add(create_request_button)

            response_text = f"❌ Для тега {tag_name} пока нет запросов."
            await bot.send_message(chat_id=callback_query.from_user.id, text=response_text,
                                   reply_markup=kb)
        if response_text != f"❌ Для тега {tag_name} пока нет запросов.":
            await bot.send_message(chat_id=callback_query.from_user.id,
                                   text='Нажмите на кнопку ниже, что посмотреть ответы.',
                                   reply_markup=await keyboards.check_answers_and_create_answer(tag_id))
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"❌ Произошла ошибка: {e}")


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
                                                                     f"🏷️ ID Тега: {tag_id}\n"
                                                                     f"🏷️ Название тега: {tag_name}\n"
                                                                     f"📝 Запрос: {request_text}\n"
                                                                     f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                                                                     f"📃 Ответы:\n"
                                                                     f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n")
                for idx, (temp_response_text, response_media, author_id, timestamp, votes, response_id) in enumerate(
                        responses, start=1):
                    response_message = f"💬 Номер ответа: {response_id}.\n👤 ID Пользователя: <code>{author_id}</code>\n👍 Количество голосов: {votes}\n🕒 Время: {timestamp}\n"
                    response_message += f"📄 Ответ: {temp_response_text}\n"
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
                await bot.send_message(chat_id=message.chat.id, text="❌ Нет ответов на данный запрос.\n",
                                       reply_markup=keyboard)

        else:
            await bot.send_message(chat_id=message.chat.id, text="❌ Вопрос с указанным номером не найден.")

    except ValueError:
        await bot.send_message(chat_id=message.chat.id, text="❌ Неверный формат ввода номера вопроса.")

    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text=f"❌ Произошла ошибка: {e}")
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
                               text=f"❌ Произошла ошибка: {e}")


class AnswerResponse(StatesGroup):
    waiting_for_response_text = State()


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('create_response_'))
async def create_response_callback(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        request_id = callback_query.data.split('_')[-1]

        async with state.proxy() as data:
            data['request_id'] = request_id

        await bot.send_message(chat_id=callback_query.from_user.id, text="Введите ваш ответ:")
        await AnswerResponse.waiting_for_response_text.set()

    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"❌ Произошла ошибка: {e}")


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

        if file_id:
            cursor.execute("""
                INSERT INTO KnowledgeResponses (request_id, author_id, response_text, response_media)
                VALUES (?, ?, ?, ?)
            """, (request_id, author_id, response_text, file_id))
        else:
            cursor.execute("""
                INSERT INTO KnowledgeResponses (request_id, author_id, response_text)
                VALUES (?, ?, ?)
            """, (request_id, author_id, response_text))

        conn.commit()

        await bot.send_message(chat_id=message.chat.id, text="✅ Ваш ответ сохранен и отправлен на модерацию")

        cursor.execute("SELECT response_text FROM KnowledgeResponses WHERE id = ?", (request_id,))
        request_text = cursor.fetchone()

        if request_text:
            request_text = request_text[0]
        else:
            request_text = "Нет текста запроса"

        id_answer = cursor.execute("SELECT id FROM KnowledgeResponses WHERE request_id =? AND author_id =? AND "
                                   "response_text =? AND response_media = ?", (request_id, author_id, response_text,
                                                                               file_id)).fetchone()[0]

        admins = cursor.execute("SELECT user_id FROM Admins").fetchall()
        for admin in admins:
            if file_id:
                if file_id.startswith("AgAC"):
                    await bot.send_photo(chat_id=admin[0], photo=file_id,
                                         caption=f"📸 Новый ответ: {request_text}\n<code>/approve_answer {id_answer}</code> или <code>/reject_answer {id_answer}</code>")
                elif file_id.startswith("BAAC"):
                    await bot.send_video(chat_id=admin[0], video=file_id,
                                         caption=f"🎥 Новый ответ: {request_text}\n<code>/approve_answer {id_answer}</code> или <code>/reject_answer {id_answer}</code>")
                elif file_id.startswith("AwAC"):
                    await bot.send_voice(chat_id=admin[0], voice=file_id,
                                         caption=f"🎤 Новый ответ: {request_text}\n<code>/approve_answer {id_answer}</code> или <code>/reject_answer {id_answer}</code>")
                elif file_id.startswith("BQAC"):
                    await bot.send_document(chat_id=admin[0], document=file_id,
                                            caption=f"📄 Новый ответ: {request_text}\n<code>/approve_answer {id_answer}</code> или <code>/reject_answer {id_answer}</code>")
                elif file_id.startswith("DQAC"):
                    await bot.send_message(chat_id=admin[0],
                                           text=f"📝 Новый ответ: {request_text}\n<code>/approve_answer {id_answer}</code> или <code>/reject_answer {id_answer}</code>")
                    await bot.send_video_note(chat_id=admin[0], video_note=file_id)
            else:
                await bot.send_message(chat_id=admin[0],
                                       text=f"📝 Новый ответ: {request_text}\n<code>/approve_answer {id_answer}</code> или <code>/reject_answer {id_answer}</code>")

        await state.finish()

    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text=f"❌ Произошла ошибка: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('vote_question_'))
async def vote_question(callback_query: types.CallbackQuery):
    try:
        request_id = int(callback_query.data.split('_')[-1])
        user_id = callback_query.from_user.id

        cursor.execute("SELECT 1 FROM QuestionVotes WHERE user_id = ? AND question_id = ?", (user_id, request_id))
        existing_vote = cursor.fetchone()

        if existing_vote:
            await bot.answer_callback_query(callback_query.id, text="❌ Вы уже голосовали за этот вопрос!")
        else:
            cursor.execute("UPDATE KnowledgeRequests SET votes = votes + 1 WHERE id = ?", (request_id,))
            cursor.execute("INSERT INTO QuestionVotes (user_id, question_id) VALUES (?, ?)", (user_id, request_id))
            conn.commit()

            await bot.answer_callback_query(callback_query.id, text="✅ Вы успешно проголосовали за вопрос!")

    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"❌ Произошла ошибка: {e}")


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('vote_response_'))
async def vote_response(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text="Введите номер ответа, за который хотите проголосовать:")

        await AnswerRequest.waiting_for_response_id.set()

        async with state.proxy() as data:
            data['response_id'] = int(callback_query.data.split('_')[-1])
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"❌ Произошла ошибка: {e}")


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
            await message.answer("❌ Вы уже голосовали за этот ответ!")
        else:
            cursor.execute("""
                UPDATE KnowledgeResponses
                SET votes = votes + 1
                WHERE id = ?
            """, (response_id,))
            conn.commit()

            cursor.execute("INSERT INTO ResponseVotes (user_id, response_id) VALUES (?, ?)", (user_id, response_id))
            conn.commit()

            await message.answer("✅ Ваш голос за ответ успешно засчитан!")

            await state.finish()

    except ValueError:
        await message.answer("❌ Неверный формат ввода номера ответа.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {e}")


if __name__ == '__main__':
    dp.register_message_handler(handler_start, commands=['start'], state='*')
    register.all_callback(dp)
    executor.start_polling(dp, skip_updates=True)
