import sqlite3

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

conn = sqlite3.connect('database.db')
cursor = conn.cursor()


async def need_notification_or_not():
    kb = InlineKeyboardMarkup()
    button_need_notification = InlineKeyboardButton(text='Да', callback_data='yes_need_notification')
    button_no_need_notification = InlineKeyboardButton(text='Нет', callback_data='no_need_notification')
    kb.add(button_need_notification, button_no_need_notification)
    return kb


async def main_menu():
    kb = InlineKeyboardMarkup()

    view_requests_btn = InlineKeyboardButton("Просмотр запросов", callback_data="view_requests")
    kb.add(view_requests_btn)

    my_requests_btn = InlineKeyboardButton("Мои запросы", callback_data="my_requests")
    kb.add(my_requests_btn)

    search_by_tags_btn = InlineKeyboardButton("Поиск по тегам", callback_data="search_by_tags")
    kb.add(search_by_tags_btn)

    check_raiting_btn = InlineKeyboardButton("Проверить рейтинг", callback_data="check_rating")
    kb.add(check_raiting_btn)

    return kb


async def button_for_tags(tag_id):
    kb = InlineKeyboardMarkup()
    view_requests_btn = InlineKeyboardButton("Просмотреть все запросы", callback_data=f"view_all_requests_{tag_id}")
    create_request_btn = InlineKeyboardButton("Создать запрос", callback_data=f"create_request_{tag_id}")
    my_requests_btn = InlineKeyboardButton("Мои запросы", callback_data=f"my_requests_{tag_id}")

    kb.add(view_requests_btn)
    kb.add(create_request_btn)
    kb.add(my_requests_btn)

    return kb


async def check_my_answer():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(text="Посмотреть ответы", callback_data="check_my_answer"),
    )
    return kb


async def check_answers_and_create_answer(tag_id):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(text="Просмотреть ответы", callback_data=f"check_answers_{tag_id}")
    )
    return kb


async def needed_sms_for_user():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="Да", callback_data="yes_need_sms"),
           InlineKeyboardButton(text="Нет", callback_data="no_need_sms"))
    return kb
