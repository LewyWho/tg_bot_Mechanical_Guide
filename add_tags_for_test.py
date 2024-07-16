import sqlite3

# Подключение к базе данных
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Запрос на добавление тегов в таблицу Tags
tags = [
    ('Машиностроение',),
    ('Производство',),
    ('Инструкции',),
    ('Telegram Бот',),
    ('Агрегатор Знаний',)
]

cursor.executemany("INSERT INTO Tags (tag_name) VALUES (?)", tags)

conn.commit()
conn.close()
