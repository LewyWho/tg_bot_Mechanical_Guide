from aiogram import types, Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sms

import keyboards
from main import cursor
from main import conn
import config

bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())


class SearchTags(StatesGroup):
    entering_tag = State()


YES_NOTIFICATION = 'yes_need_notification'
NO_NOTIFICATION = 'no_need_notification'
VIEW_REQUESTS = 'view_requests'
MY_REQUESTS = 'my_requests'


@dp.callback_query_handler(text=YES_NOTIFICATION)
async def yes_need_notification(callback_query: types.CallbackQuery):
    """Обработчик для подтверждения подписки на уведомления."""
    try:
        # Добавляем пользователя в базу данных с подпиской на уведомления
        cursor.execute("INSERT INTO Users (id, username, notification_preferences, role) VALUES (?,?,?,?)",
                       (callback_query.from_user.id, callback_query.from_user.username, 1, 0))
        conn.commit()
        await bot.send_message(chat_id=callback_query.message.chat.id,
                               text=sms.need_notification_yes())
    except Exception as e:
        await bot.send_message(chat_id=callback_query.message.chat.id,
                               text=f"Произошла ошибка: {e}")
    finally:
        await bot.send_message(chat_id=callback_query.message.chat.id,
                               text='Спасибо за прохождение небольшой регистрации :)\n/start для продолжения...')


@dp.callback_query_handler(text=NO_NOTIFICATION)
async def no_need_notification(callback_query: types.CallbackQuery):
    """Обработчик для отказа от подписки на уведомления."""
    try:
        # Добавляем пользователя в базу данных без подписки на уведомления
        cursor.execute("INSERT INTO Users (id, username, notification_preferences, role) VALUES (?,?,?,?)",
                       (callback_query.from_user.id, callback_query.from_user.username, 0, 0))
        conn.commit()
        await bot.send_message(chat_id=callback_query.message.chat.id,
                               text=sms.need_notification_no())
    except Exception as e:
        await bot.send_message(chat_id=callback_query.message.chat.id,
                               text=f"Произошла ошибка: {e}")
    finally:
        await bot.send_message(chat_id=callback_query.message.chat.id,
                               text='Спасибо за прохождение небольшой регистрации :)\n/start для продолжения...')


@dp.callback_query_handler(text=VIEW_REQUESTS)
async def view_requests(callback_query: types.CallbackQuery):
    """Обработчик для просмотра запросов по тегам."""
    try:
        # Получаем список тегов из базы данных
        tags = cursor.execute("SELECT id, tag_name FROM Tags").fetchall()
        keyboard = InlineKeyboardMarkup()
        for tag_id, tag_name in tags:
            button = InlineKeyboardButton(text=tag_name, callback_data=f"select_tag_{tag_id}")
            keyboard.add(button)

        await bot.send_message(chat_id=callback_query.from_user.id,
                               text="Выберите тег:", reply_markup=keyboard)
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text=f"Произошла ошибка: {e}")


CURRENT_PAGE = 1
TOTAL_PAGES = 1


@dp.callback_query_handler(text=MY_REQUESTS)
async def my_requests(callback_query: types.CallbackQuery):
    try:
        global CURRENT_PAGE, TOTAL_PAGES

        user_id = callback_query.from_user.id

        # Получаем все запросы пользователя с соответствующими тегами
        cursor.execute("""
            SELECT kr.id, kr.request_text, kr.id_tag
            FROM KnowledgeRequests kr
            WHERE kr.author_id = ?
        """, (user_id,))

        user_requests = cursor.fetchall()

        if user_requests:
            TOTAL_PAGES = (len(user_requests) + 4) // 5  # Определяем общее количество страниц
            response_text = format_requests(user_requests)
            await send_requests_message(user_id, response_text)
        else:
            await bot.send_message(chat_id=user_id, text="У вас пока нет запросов.")

    except Exception as e:
        await bot.send_message(chat_id=user_id, text=f"Произошла ошибка: {e}")


async def send_requests_message(user_id, response_text):
    """Отправляет сообщение с запросами и соответствующими кнопками."""
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = []

    if CURRENT_PAGE > 1:
        buttons.append(InlineKeyboardButton(text="Назад", callback_data="back_page"))

    if CURRENT_PAGE < TOTAL_PAGES:
        buttons.append(InlineKeyboardButton(text="Вперед", callback_data="next_page"))

    keyboard.add(*buttons)
    await bot.send_message(chat_id=user_id, text=response_text, reply_markup=keyboard)


def format_requests(requests):
    """Форматирует список запросов для вывода."""
    start_idx = (CURRENT_PAGE - 1) * 5
    end_idx = min(start_idx + 5, len(requests))

    response_text = "Ваши запросы:\n"
    for idx, (request_id, request_text, tag_id) in enumerate(requests[start_idx:end_idx], start=start_idx + 1):
        response_text += f"{idx}. Запрос: {request_text}\n"
        if tag_id is not None:
            tag_name = cursor.execute("SELECT tag_name FROM Tags WHERE id = ?", (tag_id,)).fetchone()
            response_text += f"   Тег: {tag_name[0]}\n"
        response_text += "=====================\n"

    return response_text


@dp.callback_query_handler(text="back_page")
async def back_page(callback_query: types.CallbackQuery):
    """Обработчик для кнопки 'Назад'."""
    try:
        global CURRENT_PAGE
        if CURRENT_PAGE > 1:
            CURRENT_PAGE -= 1
            await my_requests(callback_query)
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


@dp.callback_query_handler(text="next_page")
async def next_page(callback_query: types.CallbackQuery):
    """Обработчик для кнопки 'Вперед'."""
    try:
        global CURRENT_PAGE
        if CURRENT_PAGE < TOTAL_PAGES:
            CURRENT_PAGE += 1
            await my_requests(callback_query)
    except Exception as e:
        await bot.send_message(chat_id=callback_query.from_user.id, text=f"Произошла ошибка: {e}")


@dp.callback_query_handler(text="search_by_tags")
async def search_by_tags(callback_query: types.CallbackQuery):
    try:
        user_id = callback_query.from_user.id

        await bot.send_message(chat_id=user_id, text="Введите тег:")
        await SearchTags.entering_tag.set()

    except Exception as e:
        await bot.send_message(chat_id=user_id, text=f"Произошла ошибка: {e}")


@dp.message_handler(state=SearchTags.entering_tag)
async def process_entering_tag(message: types.Message, state: FSMContext):
    try:
        tag = message.text.strip()

        # Проверяем наличие введенного тега в базе данных
        cursor.execute("SELECT id, tag_name FROM Tags WHERE tag_name LIKE ?", (f"%{tag}%",))
        found_tags = cursor.fetchall()

        if found_tags:
            keyboard = InlineKeyboardMarkup(row_width=1)
            buttons = [InlineKeyboardButton(text=tag[1], callback_data=f"select_tag_{tag[0]}") for tag in found_tags]
            keyboard.add(*buttons)

            await bot.send_message(chat_id=message.chat.id, text="Выберите тег из списка:", reply_markup=keyboard)
        else:
            await bot.send_message(chat_id=message.chat.id, text="По вашему запросу ничего не найдено.")

        await state.finish()

    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text=f"Произошла ошибка: {e}")
