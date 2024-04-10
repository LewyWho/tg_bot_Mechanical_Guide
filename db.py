import sqlite3

# Подключение к базе данных
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Таблица для запросов на знания
cursor.execute('''
CREATE TABLE IF NOT EXISTS KnowledgeRequests (
    id INTEGER PRIMARY KEY,
    author_id INTEGER,
    request_text TEXT,
    request_media TEXT, -- Для хранения медиа-файлов
    id_tag INTEGER,
    votes INTEGER DEFAULT 0, -- Количество голосов
    vote_author_id INTEGER, -- Идентификатор автора голосования
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, -- Дата и время создания
    moderated BOOLEAN DEFAULT FALSE -- Пометка о модерации администратором
);
''')

# Таблица для ответов на запросы на знания
cursor.execute('''
CREATE TABLE IF NOT EXISTS KnowledgeResponses (
    id INTEGER PRIMARY KEY,
    request_id INTEGER, -- Ссылка на идентификатор запроса
    tag_id INTEGER,
    author_id INTEGER,
    response_text TEXT,
    response_media TEXT, -- Для хранения медиа-файлов
    votes INTEGER DEFAULT 0, -- Количество голосов
    vote_author_id INTEGER, -- Идентификатор автора голосования
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, -- Дата и время создания
    moderated BOOLEAN DEFAULT FALSE -- Пометка о модерации администратором
);
''')

# Таблица для пользователей
cursor.execute('''
CREATE TABLE IF NOT EXISTS Users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    needed_sms_for_user INTEGER,
    notification_preferences INTEGER default 0, -- Настройки уведомлений
    role INTEGER, -- Роль пользователя (сотрудник, администратор и т.д.)
    rank_user TEXT default 'Новичок'
);
''')


# Таблица для тегов
cursor.execute('''
CREATE TABLE IF NOT EXISTS Tags (
    id INTEGER PRIMARY KEY,
    tag_name TEXT UNIQUE
);
''')

# Таблица для рассылки новых запросов на знания
cursor.execute('''
CREATE TABLE IF NOT EXISTS Subscriptions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    tag_id INTEGER, -- Для фильтрации по тегам
    frequency INTEGER, -- Частота рассылки (В секундах),
    FOREIGN KEY (user_id) REFERENCES Users(id),
    FOREIGN KEY (tag_id) REFERENCES Tags(id)
);
''')

# Таблица для администраторов
cursor.execute('''
CREATE TABLE IF NOT EXISTS Admins (
    user_id INTEGER UNIQUE,
    password TEXT
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS QuestionVotes (
    user_id INTEGER,
    question_id INTEGER,
    PRIMARY KEY (user_id, question_id)
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS ResponseVotes (
    user_id INTEGER,
    response_id INTEGER,
    PRIMARY KEY (user_id, response_id)
);
''')

conn.commit()
conn.close()
