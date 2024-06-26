<h1 style="text-align: center;">Телеграм Бот для Хакатона</h1>
<p>Этот проект представляет собой Telegram бота, разработанный для управления запросами на знания (инструкции) среди сотрудников компании. Бот поддерживает различные функциональности в соответствии с требованиями к хакатону.</p>

<h2>Описание функциональностей</h2>
<ul>
    <li><strong>Голосование за запросы на знания:</strong> Сотрудники могут голосовать за запросы, которые, по их мнению, являются наиболее важными.</li>
    <li><strong>Отображение запросов в порядке убывания голосов:</strong> Запросы на знания отображаются в боте в порядке убывания количества голосов.</li>
    <li><strong>Голосование за ответы на запросы:</strong> Сотрудники могут также голосовать за ответы на запросы на знания.</li>
    <li><strong>Отображение ответов в порядке убывания голосов:</strong> Ответы на запросы также отображаются в порядке убывания количества голосов.</li>
    <li><strong>Система тегов:</strong> Пользователи могут добавлять теги к запросам на знания, обозначающие их тематику.</li>
    <li><strong>Поиск по тегам:</strong> Сотрудники имеют возможность искать запросы на знания по тегам.</li>
    <li><strong>Подписка на рассылку новых запросов:</strong> Пользователи могут подписаться на рассылку новых запросов на знания по выбранным тегам.</li>
    <li><strong>Уведомления о ответах на запросы:</strong> Сотрудники могут подписаться на уведомления о новых ответах на запросы, на которые они отправляли запросы.</li>
    <li><strong>Отправка запросов в различных форматах:</strong> Помимо текста, сотрудники могут отправлять запросы на знание в виде изображений, видео, звуковых файлов или голосовых сообщений.</li>
    <li><strong>Отправка ответов в различных форматах:</strong> Аналогично запросам, ответы на запросы могут быть отправлены в различных форматах.</li>
    <li><strong>Редактирование отправленных запросов:</strong> Сотрудники могут вернуться к своим отправленным запросам на знания и отредактировать их.</li>
    <li><strong>Редактирование отправленных ответов:</strong> Аналогично запросам, сотрудники могут редактировать отправленные ими ответы на запросы на знания.</li>
    <li><strong>Раздел с авторами запросов и ответов:</strong> В боте присутствует раздел, где указан список авторов запросов и ответов с их контактными данными. Авторы сортируются по количеству отправленных ответов.</li>
    <li><strong>Раздел администратора для модерации запросов:</strong> Раздел администратора позволяет модерировать запросы на знания перед их публикацией. Администратор может принять или отклонить запрос, уведомление об этом отправляется автору.</li>
    <li><strong>Раздел администратора для модерации ответов:</strong> Аналогично запросам, администратор может модерировать ответы на запросы на знание перед их публикацией.</li>
    <li><strong>Массовая рассылка знаний:</strong> Администратор может осуществлять массовую рассылку знаний о процессах на производстве. Уведомление об этом отправляется всем сотрудникам.</li>
</ul>

<h2>Установка и настройка</h2>
<ol>
    <li>Клонируйте репозиторий:</li>
    <pre><code>git clone https://github.com/LewyWho/tg_bot_Mechanical_Guide.git</code></pre>
    <li>Установите зависимости:</li>
    <pre><code>pip install -r requirements.txt</code></pre>
    <li>Откройте файл конфигурации <code>config.py</code> и заполните необходимые параметры.</li>
    <li>Запустите бота:</li>
    <pre><code>python main.py</code></pre>
</ol>

<h2>Использование</h2>
<ol>
    <li>Начните диалог с ботом в Telegram.</li>
    <li>Используйте команды и кнопки, чтобы взаимодействовать с функциональностями бота.</li>
</ol>

<h2>Вклад и обратная связь</h2>
<p>Если у вас есть предложения по улучшению проекта, пожалуйста, создайте issue или отправьте pull request на GitHub.</p>
