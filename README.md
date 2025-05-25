# 📄 EDMS — Система управления документами

**EDMS** (Electronic Document Management System) — это мощная система управления документами на базе Django, разработанная для продакшен-использования. Она позволяет создавать, редактировать, подписывать и управлять документами с поддержкой безопасной авторизации, загрузки файлов и автоматических email-уведомлений. Проект идеально подходит для организаций, которым нужна надежная и гибкая платформа для работы с документами.

🌟 **Ключевые возможности**:

- 📝 Создание и редактирование документов с загрузкой файлов.
- 🖋️ Поддержка электронных подписей для документов.
- 🔍 Поиск пользователей по email для назначения подписантов.
- 📧 Email-уведомления через SMTP (например, `smtp.mail.ru`).
- 🗑️ Удаление документов с подтверждением через модальное окно.
- 📂 Управление входящими и исходящими документами.
- 🔐 Безопасная авторизация и управление доступом (владелец/админ).
- 📜 Логирование всех действий с документами.
- 🔒 Продакшен-настройки безопасности (HTTPS, HSTS, CSRF).

---

## 📋 Содержание

- [🌟 О проекте](#-о-проекте)
- [🔑 Ключевые возможности](#-ключевые-возможности)
- [🚀 Начало работы](#-начало-работы)
  - [📋 Требования](#-требования)
  - [🛠️ Установка](#-установка)
  - [⚙️ Настройка PostgreSQL](#-настройка-postgresql)
  - [📧 Настройка SMTP](#-настройка-smtp)
  - [🌐 Настройка продакшен-домена](#-настройка-продакшен-домена)
  - [🔄 Применение миграций](#-применение-миграций)
  - [👤 Создание суперпользователя](#-создание-суперпользователя)
  - [📂 Сбор статических файлов](#-сбор-статических-файлов)
  - [🏁 Запуск сервера](#-запуск-сервера)
- [📖 Использование](#-использование)
  - [📝 Создание документа](#-создание-документа)
  - [✍️ Редактирование документа](#-редактирование-документа)
  - [⬇️ Скачивание файлов](#-скачивание-файлов)
  - [🖋️ Подписание документа](#-подписание-документа)
  - [🔔 Уведомления](#-уведомления)
- [🗂️ Структура проекта](#-структура-проекта)
- [🛡️ Устранение неполадок](#-устранение-неполадок)
- [📬 Контакты](#-контакты)

---

## 🚀 Начало работы

Следуйте этим шагам, чтобы настроить и запустить EDMS локально или в продакшене.

### 📋 Требования

- 🐍 Python 3.11+
- 🗄️ PostgreSQL 15+
- 📦 Git
- 📧 SMTP-сервер (например, `smtp.mail.ru` или Gmail)
- 🔧 `python-decouple` для работы с `.env`

### 🛠️ Установка

1. **Клонируйте репозиторий**:

   ```bash
   git clone https://github.com/NeonchikMPT/EDMS.git
   cd EDMS
   ```

2. **Создайте и активируйте виртуальное окружение**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

3. **Установите зависимости**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Создайте файл `.env`**:

   В корне проекта создайте файл `.env` и добавьте настройки:

   ```env
   # База данных
   DB_NAME=edms_db
   DB_USER=postgres
   DB_PASSWORD=your_password
   DB_HOST=localhost
   DB_PORT=5432

   # Секретный ключ
   SECRET_KEY=your_secret_key

   # Email
   EMAIL_HOST_PASSWORD=your_smtp_password

   # Режим отладки
   DJANGO_DEBUG=False
   ```

   > **Примечание**: Замените `your_password`, `your_secret_key`, и `your_smtp_password` на свои значения. Для `smtp.mail.ru` используйте пароль приложения.

5. **Настройте PostgreSQL**:

   - Создайте базу данных:

     ```bash
     createdb edms_db
     ```

   - Убедитесь, что настройки в `edms/settings.py` соответствуют `.env`:

     ```python
     DATABASES = {
         'default': {
             'ENGINE': 'django.db.backends.postgresql',
             'NAME': config('DB_NAME', default='edms_db'),
             'USER': config('DB_USER', default='postgres'),
             'PASSWORD': config('DB_PASSWORD'),
             'HOST': config('DB_HOST', default='localhost'),
             'PORT': config('DB_PORT', default='5432'),
         }
     }
     ```

6. **Настройте SMTP**:

   В `edms/settings.py` уже настроен SMTP для `smtp.mail.ru`:

   ```python
   EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
   EMAIL_HOST = 'smtp.mail.ru'
   EMAIL_PORT = 465
   EMAIL_USE_SSL = True
   EMAIL_HOST_USER = 'dsistema@internet.ru'
   EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
   DEFAULT_FROM_EMAIL = 'dsistema@internet.ru'
   ```

   Убедитесь, что `EMAIL_HOST_PASSWORD` в `.env` корректен.

7. **Настройте продакшен-домен**:

   В `edms/settings.py` обновите `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS`:

   ```python
   ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com', '127.0.0.1', 'localhost']
   CSRF_TRUSTED_ORIGINS = ['https://yourdomain.com', 'https://www.yourdomain.com']
   ```

   Для локального тестирования оставьте `127.0.0.1` и `localhost`.

8. **Примените миграции**:

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

9. **Создайте суперпользователя**:

   ```bash
   python manage.py createsuperuser
   ```

10. **Соберите статические файлы** (для продакшена):

    ```bash
    python manage.py collectstatic
    ```

11. **Запустите сервер**:

    ```bash
    python manage.py runserver
    ```

12. **Откройте приложение**:

    Перейдите по адресу `http://127.0.0.1:8000/` (или `https://yourdomain.com` в продакшене) и войдите как суперпользователь.

---

## 📖 Использование

1. **Создание документа**:

   - Перейдите в раздел «Создать документ» (`/docs/create/`).
   - Укажите название, загрузите файл и выберите подписантов через поиск по email.
   - Если подписанты не выбраны, документ сохраняется как черновик.

2. **Редактирование документа**:

   - В разделе «Мои документы» (`/docs/my-documents/`) выберите документ.
   - Измените название, замените файл или обновите подписантов.
   - Нажмите «Удалить» для полного удаления (с подтверждением в модальном окне).

3. **Скачивание файлов**:

   - В форме редактирования кликните на имя текущего файла для скачивания.

4. **Подписание документа**:

   - В разделе «Входящие» (`/docs/received/`) найдите документы, требующие подписи.
   - Нажмите «Подписать» для подтверждения.

5. **Уведомления**:

   - Проверяйте уведомления в разделе «Уведомления» (`/docs/notifications/`).
   - Новые документы, комментарии и обновления отправляют email-уведомления.

---

## 🗂️ Структура проекта

```plaintext
EDMS/
├── media/               # Медиа-файлы
│   ├── avatars/            # Аватарки
│   └── docs/            # Документы
├── static/               # Статические файлы (favicon.ico, audio/notification.mp3)
├── users/               # Приложение для пользователей
├── docs/               # Приложение для документов
├── templates/           # HTML-шаблоны
├── edms/               # Настройки проекта
├── manage.py           # Управление проектом
├── .env                     # Переменные окружения
├── requirements.txt     # Зависимости
└── README.md           # Документация
```

---

## 🛡️ Устранение неполадок

| Проблема | Решение |
| --- | --- |
| **Ошибка базы данных** | Проверьте `.env` и `settings.py` (`DB_NAME`, `DB_USER`, `DB_PASSWORD`). Убедитесь, что PostgreSQL запущен: `psql -U postgres`. |
| **Медиа-файлы не загружаются** | Убедитесь, что формы используют `enctype="multipart/form-data"`. Проверьте существование папок `media/avatars/` и `media/docs/`. |
| **Файлы не скачиваются** | Добавьте в `edms/urls.py`: `urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)`. Проверьте `MEDIA_URL` и `MEDIA_ROOT`. |
| **Дублирующиеся сообщения** | В `docs/views.py` (`document_create`, `document_edit`) используйте одно сообщение: `messages.success` для `sent`, `messages.warning` для `draft`. |
| **Кнопка удаления не работает** | Проверьте маршрут `document_delete` в `docs/urls.py` и модальное окно в `document_edit.html`. Убедитесь, что Bootstrap 5 подключен в `base.html`. |
| **Email не отправляется** | Проверьте `EMAIL_HOST_PASSWORD` в `.env`. Убедитесь, что `smtp.mail.ru` настроен корректно и использует пароль приложения. |
| **Ошибка 403/404 в продакшене** | Обновите `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` в `settings.py`. Убедитесь, что `DEBUG=False` и HTTPS настроен. |
| **Статические файлы не отображаются** | Выполните `python manage.py collectstatic`. Проверьте `STATIC_URL`, `STATICFILES_DIRS`, `STATIC_ROOT`. |
| **Ошибка миграций** | Удалите старые миграции: `del /s /q migrations\*.py` (Windows, сохраните `__init__.py`), затем выполните `makemigrations` и `migrate`. |

**Дополнительные шаги**:

- Проверьте логи сервера:

  ```bash
  python manage.py runserver
  ```

- Проверьте пути к файлам:

  ```bash
  python manage.py shell
  ```

  ```python
  from docs.models import Document
  doc = Document.objects.get(id=1)
  print(doc.file.url)  # Должно вывести /media/docs/<filename>
  ```

---

## 📬 Контакты

Автор: NeonchikMPT

По вопросам и предложениям обращайтесь через [GitHub Issues](https://github.com/NeonchikMPT/EDMS/issues).

⭐ **Поставьте звезду проекту, если он вам понравился!**
