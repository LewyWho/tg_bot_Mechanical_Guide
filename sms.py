import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()


def message_start():
    return """Добро пожаловать в Telegram бот-агрегатор знаний о процессах машиностроительного производства! 🤖🏭
    
Здесь вы найдете ответы на различные вопросы, связанные с процессами и инструкциями по работе на предприятиях машиностроения. 

Наш бот поможет вам быстро находить нужную информацию, голосовать за лучшие запросы и ответы, подписываться на интересующие темы и многое другое."""


def register_start():
    return """Для начала работы с ботом необходимо зарегистрироваться."""


def need_notification_or_not():
    return """❓Хотите получать уведомления о новых ответах на ваши вопросы?"""


def need_notification_yes():
    return """Теперь вы можете получать уведомления о новых ответах на ваши вопросы."""


def need_notification_no():
    return """Теперь вы не будете получать уведомления о новых ответах на ваши вопросы."""


def get_user_questions_count(user_id):
    cursor.execute("SELECT * FROM KnowledgeRequests WHERE author_id=?", (user_id,))
    result = cursor.fetchone()
    if result:
        count = result[0]
    else:
        count = 0
    return count


def get_user_role(user_id):
    cursor.execute("SELECT role FROM Users WHERE id=?", (user_id,))
    role = cursor.fetchone()[0]
    return role


def get_user_responses_count(user_id):
    cursor.execute("SELECT * FROM KnowledgeResponses WHERE author_id=?", (user_id,))
    result = cursor.fetchone()
    if result:
        count = result[0]
    else:
        count = 0
    return count


def get_user_rank(user_id):
    cursor.execute(
        "SELECT SUM(votes) FROM KnowledgeRequests WHERE author_id=?", (user_id,))
    num_votes_for_result = cursor.fetchone()
    num_votes_for = num_votes_for_result[0] if num_votes_for_result[0] is not None else 0

    cursor.execute(
        "SELECT SUM(votes) FROM KnowledgeResponses WHERE author_id=?", (user_id,))
    num_votes_against_result = cursor.fetchone()
    num_votes_against = num_votes_against_result[0] if num_votes_against_result[0] is not None else 0

    total_votes = num_votes_for + num_votes_against

    if total_votes < 5:
        cursor.execute("UPDATE Users SET rank_user='Новичок' WHERE id=?", (user_id,))
    elif 5 <= total_votes < 10:
        cursor.execute("UPDATE Users SET rank_user='Ученик' WHERE id=?", (user_id,))
    elif 10 <= total_votes < 20:
        cursor.execute("UPDATE Users SET rank_user='Знаток' WHERE id=?", (user_id,))
    elif 20 <= total_votes < 30:
        cursor.execute("UPDATE Users SET rank_user='Профи' WHERE id=?", (user_id,))
    elif 30 <= total_votes < 40:
        cursor.execute("UPDATE Users SET rank_user='Мастер' WHERE id=?", (user_id,))
    elif 40 <= total_votes < 50:
        cursor.execute("UPDATE Users SET rank_user='Гуру' WHERE id=?", (user_id,))
    elif 50 <= total_votes < 60:
        cursor.execute("UPDATE Users SET rank_user='Мыслитель' WHERE id=?", (user_id,))
    elif 60 <= total_votes < 70:
        cursor.execute("UPDATE Users SET rank_user='Мудрец' WHERE id=?", (user_id,))
    elif 70 <= total_votes < 80:
        cursor.execute("UPDATE Users SET rank_user='Просветленный' WHERE id=?", (user_id,))
    elif 80 <= total_votes < 90:
        cursor.execute("UPDATE Users SET rank_user='Оракул' WHERE id=?", (user_id,))
    elif 90 <= total_votes < 100:
        cursor.execute("UPDATE Users SET rank_user='Гений' WHERE id=?", (user_id,))
    elif 100 <= total_votes < 150:
        cursor.execute("UPDATE Users SET rank_user='Искусственный Интеллект' WHERE id=?", (user_id,))
    elif total_votes >= 150:
        cursor.execute("UPDATE Users SET rank_user='Высший разум' WHERE id=?", (user_id,))
    conn.commit()


def profile_user(user_id):
    get_user_rank(user_id)

    num_questions = get_user_questions_count(user_id)
    num_responses = get_user_responses_count(user_id)

    result_first = cursor.execute("SELECT SUM(votes) FROM KnowledgeRequests WHERE author_id=? AND moderated = 1",
                                  (user_id,)).fetchone()
    num_votes_for = result_first[0] if result_first[0] is not None else 0

    result_second = cursor.execute(
        "SELECT SUM(votes) FROM KnowledgeResponses WHERE author_id=? AND moderated = 1",
        (user_id,)).fetchone()
    num_votes_against = result_second[0] if result_second[0] is not None else 0

    role = get_user_role(user_id)
    role_str = "Сотрудник" if role == 0 else "Администратор"

    rank_user = cursor.execute("SELECT rank_user FROM Users WHERE id=?", (user_id,)).fetchone()[0]

    profile_info = f"""Ваш профиль:
➖➖➖➖➖➖➖➖➖➖➖➖➖➖
🆔 Ваш ID: {user_id}
📝 Количество ваших вопросов: {num_questions}
💬 Количество ваших ответов: {num_responses}
👍 Количество голосов для ваших вопросов: {num_votes_for}
👍Количество голосов для ваших ответов: {num_votes_against}
👤 Ваша роль: {role_str}
🏅 Ваш ранг: {rank_user}
➖➖➖➖➖➖➖➖➖➖➖➖➖➖"""

    if role == 1:
        profile_info += "\n/admin_help - Список всех команд для администратора"

    profile_info += "\n/help - Вывод всех доступных команд\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖"

    return profile_info


def get_tag(tag):
    return f"""Вы выбрали следующий тег: {tag}\n\nЧто вы хотите сделать?"""


def needed_sms_for_user():
    return """Хотите ли вы получать сообщения от пользователей?"""


def help_message():
    return """Все доступные команды:
➖➖➖➖➖➖➖➖➖➖➖➖➖➖
/start - Перейти на главную страницу бота
/my_settings - мои настройки
/a_change - изменить свой ответ
/q_change - изменить свой вопрос
/users - список всех пользователей бота
/login - войти как администратор
/sms - отправить сообщение пользователю
/cancel - отменить действие
➖➖➖➖➖➖➖➖➖➖➖➖➖➖"""


def admin_help():
    return """Все доступные команды для администратора:
➖➖➖➖➖➖➖➖➖➖➖➖➖➖
/check_answers - Модерация ответов
/check_questions - Модерация вопросов
/mailing - Массовая отправка сообщений
/delete_user - Удаление пользователя
/ban_user - Блокировка пользователя
/unban_user - Разблокировка пользователя
/sms_user - Отправка сообщения пользователю
➖➖➖➖➖➖➖➖➖➖➖➖➖➖"""