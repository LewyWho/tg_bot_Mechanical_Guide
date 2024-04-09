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
    return """Хотите получать уведомления о новых ответах на ваши вопросы?"""


def need_notification_yes():
    return """Теперь вы можете получать уведомления о новых ответах на ваши вопросы."""


def need_notification_no():
    return """Теперь вы не будете получать уведомления о новых ответах на ваши вопросы."""


def get_user_questions_count(user_id):
    cursor.execute("SELECT COUNT(*) FROM KnowledgeRequests WHERE author_id=?", (user_id,))
    count = cursor.fetchone()[0]
    return count


def get_user_role(user_id):
    cursor.execute("SELECT role FROM Users WHERE id=?", (user_id,))
    role = cursor.fetchone()[0]
    return role


def get_user_votes(user_id):
    cursor.execute("SELECT vote_type, COUNT(*) FROM Votes WHERE user_id=? GROUP BY vote_type", (user_id,))
    votes = cursor.fetchall()
    num_votes_for = num_votes_against = 0
    for vote_type, count in votes:
        if vote_type == "За":
            num_votes_for = count
        elif vote_type == "Против":
            num_votes_against = count
    return num_votes_for, num_votes_against


def get_user_responses_count(user_id):
    cursor.execute("SELECT COUNT(*) FROM KnowledgeResponses WHERE author_id=?", (user_id,))
    count = cursor.fetchone()[0]
    return count


def profile_user(user_id):
    num_questions = get_user_questions_count(user_id)
    num_responses = get_user_responses_count(user_id)
    num_votes_for = cursor.execute("SELECT COUNT(votes) FROM KnowledgeRequests WHERE author_id=? AND votes ='1'", (user_id,)).fetchone()[0]
    num_votes_against = cursor.execute("SELECT COUNT(votes) FROM KnowledgeResponses WHERE author_id=? AND votes ='1'", (user_id,)).fetchone()[0]
    role = get_user_role(user_id)
    role_str = "Сотрудник" if role == 0 else "Администратор"
    return f"""Ваш профиль:
➖➖➖➖➖➖➖➖➖➖➖➖➖➖
Ваш ID: {user_id}
Количество ваших вопросов: {num_questions}
Количество ваших ответов: {num_responses}
Количество голосов для ваших вопросов: {num_votes_for}
Количество голосов для ваших ответов: {num_votes_against}
Ваша роль: {role_str}
➖➖➖➖➖➖➖➖➖➖➖➖➖➖"""


def get_tag(tag):
    return f"""Вы выбрали следующий тег: {tag}\n\nЧто вы хотите сделать?"""
