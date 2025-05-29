import os
import subprocess
from django.core.files.base import ContentFile
from django.urls import reverse
import datetime
import pytz
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from io import StringIO
import csv
import psycopg2
import tempfile
import atexit
import re

from docs.decorators import admin_required
from docs.views import error_403
from .forms import RegisterForm, ProfileForm, LoginForm, PasswordResetRequestForm, PasswordResetForm, UserProfileForm
from .models import User, PasswordResetToken
from docs.models import Document
from django.db import IntegrityError

@admin_required
def user_list(request):
    users = User.objects.order_by('full_name')
    form = RegisterForm()

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            return JsonResponse({
                'success': True,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'full_name': user.full_name,
                    'role': user.role,
                    'role_display': user.get_role_display(),
                    'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M'),
                    'email_notifications': user.email_notifications,
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)

    return render(request, 'users/user_list.html', {'users': users, 'form': form})

@admin_required
def user_documents(request, user_id):
    user = get_object_or_404(User, id=user_id)
    docs = Document.objects.filter(owner=user).order_by('-created_at')
    return render(request, 'users/user_documents.html', {'user': user, 'docs': docs})

@login_required
def user_edit(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.user.role != 'admin' and request.user != user:
        return error_403(request)
    if request.method == 'POST':
        if 'delete_avatar' in request.POST:
            if user.avatar:
                user.avatar.delete()
            user.avatar = None
            user.save()
            messages.success(request, 'Аватар удалён.')
            return redirect('user_edit', user_id=user.id)

        try:
            user.email = request.POST.get('email', '').strip()
            user.full_name = request.POST.get('full_name', '').strip()
            user.email_notifications = 'email_notifications' in request.POST
            if request.user.role == 'admin':
                user.role = request.POST.get('role', 'staff')

            if 'avatar' in request.FILES:
                user.avatar = request.FILES['avatar']

            new_password = request.POST.get('new_password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()
            if new_password and confirm_password:
                if new_password != confirm_password:
                    messages.error(request, 'Пароли не совпадают.')
                    return render(request, 'users/user_edit.html', {'user': user})
                if len(new_password) < 8:
                    messages.error(request, 'Пароль должен содержать минимум 8 символов.')
                    return render(request, 'users/user_edit.html', {'user': user})
                user.set_password(new_password)

            user.save()

            if user == request.user and new_password:
                user = authenticate(request, username=user.email, password=new_password)
                if user:
                    login(request, user)
                    messages.success(request, 'Пользователь успешно обновлён.')
                else:
                    messages.error(request, 'Ошибка при обновлении сессии после смены пароля.')
                    return render(request, 'users/user_edit.html', {'user': user})
            else:
                messages.success(request, 'Пользователь успешно обновлён.')

            return redirect('user_edit', user_id=user.id)
        except IntegrityError as e:
            if 'Duplicate entry' in str(e):
                messages.error(request, 'Этот email уже используется другим пользователем.')
            else:
                messages.error(request, f'Ошибка при сохранении: {str(e)}')
            return render(request, 'users/user_edit.html', {'user': user})

    return render(request, 'users/user_edit.html', {'user': user})

@admin_required
def user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        if user != request.user:
            user.delete()
            messages.success(request, 'Пользователь удалён')
        else:
            return error_403(request)  # Нельзя удалить себя
        return redirect('user_list')
    return render(request, 'users/user_delete.html', {'user': user})

@login_required
def profile_view(request):
    if request.method == 'POST':
        if 'delete_avatar' in request.POST:
            if request.user.avatar:
                request.user.avatar.delete()
                request.user.avatar = None
                request.user.save()
                messages.success(request, 'Аватар удалён')
                return redirect('profile')

        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.email = request.POST.get('email', '').strip()

                new_password = form.cleaned_data.get('new_password', '').strip()
                confirm_password = form.cleaned_data.get('confirm_password', '').strip()
                if new_password and confirm_password:
                    if new_password != confirm_password:
                        messages.error(request, 'Пароли не совпадают.')
                        return render(request, 'users/profile.html', {'form': form})
                    if len(new_password) < 8:
                        messages.error(request, 'Пароль должен содержать минимум 8 символов.')
                        return render(request, 'users/profile.html', {'form': form})
                    user.set_password(new_password)

                user.save()
                print(f"Profile updated for {user.email}, email_notifications: {user.email_notifications}")

                if new_password:
                    user = authenticate(request, username=user.email, password=new_password)
                    if user:
                        login(request, user)
                        messages.success(request, 'Профиль обновлён')
                    else:
                        messages.error(request, 'Ошибка при обновлении сессии после смены пароля')
                        return render(request, 'users/profile.html', {'form': form})
                else:
                    messages.success(request, 'Профиль обновлён')

                return redirect('profile')
            except IntegrityError as e:
                if 'Duplicate entry' in str(e):
                    messages.error(request, 'Этот email уже используется другим пользователем.')
                else:
                    messages.error(request, f'Ошибка при сохранении: {str(e)}')
                return render(request, 'users/profile.html', {'form': form})
        else:
            print(f"Form validation failed for {request.user.email}: {form.errors}")
            messages.error(request, 'Ошибка при обновлении профиля: проверьте введённые данные')
            return render(request, 'users/profile.html', {'form': form})
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'users/profile.html', {'form': form})

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.role = 'staff'
            user.save()
            messages.success(request, 'Регистрация успешна')
            print(f"Registration successful for {user.email}")
            return redirect('login')
        else:
            print(f"Form validation failed: {form.errors}")
    else:
        form = RegisterForm()
    return render(request, 'users/register.html', {'form': form})

def login_view(request):
    form = LoginForm()
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                user = User.objects.get(email=email)
                user = authenticate(request, username=email, password=password)
                if user:
                    login(request, user)
                    print(f"Login successful for {user.email}, redirecting to /")
                    return redirect('/')
                else:
                    messages.error(request, 'Неверные данные')
            except User.DoesNotExist:
                messages.error(request, 'Неверные данные')
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@admin_required
def export_import(request):
    if request.user.role != 'admin':
        return error_403(request)

    if request.method == 'POST':
        # Экспорт
        if 'export_type' in request.POST:
            export_type = request.POST.get('export_type')
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            db_settings = settings.DATABASES['default']
            db_name = db_settings['NAME']
            db_user = db_settings['USER']
            db_password = db_settings['PASSWORD']
            db_host = db_settings['HOST']
            db_port = db_settings['PORT']

            if export_type == 'users_csv':
                # Экспорт пользователей в CSV
                output = StringIO()
                writer = csv.writer(output)
                writer.writerow(['Email', 'ID', 'Full Name', 'Role', 'Date Joined', 'Password', 'Avatar Path'])
                users = User.objects.all()
                for user in users:
                    avatar_path = os.path.relpath(user.avatar.path, settings.MEDIA_ROOT) if user.avatar else ''
                    writer.writerow([
                        user.email,
                        user.id,
                        user.full_name,
                        user.role,
                        user.date_joined.strftime('%Y-%m-%d %H:%M'),
                        user.password,
                        avatar_path
                    ])
                response = HttpResponse(output.getvalue(), content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="users_{timestamp}.csv"'
                return response

            elif export_type == 'documents_csv':
                # Экспорт документов в CSV
                output = StringIO()
                writer = csv.writer(output)
                writer.writerow(['ID', 'Title', 'Status', 'Owner', 'Recipients', 'Created At', 'File Path'])
                docs = Document.objects.all()
                for doc in docs:
                    recipients = ', '.join(doc.recipients.values_list('email', flat=True))
                    file_path = os.path.relpath(doc.file.path, settings.MEDIA_ROOT) if doc.file else ''
                    writer.writerow([
                        doc.id,
                        doc.title,
                        doc.status,
                        doc.owner.email,
                        recipients,
                        doc.created_at.strftime('%Y-%m-%d %H:%M'),
                        file_path
                    ])
                response = HttpResponse(output.getvalue(), content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="documents_{timestamp}.csv"'
                return response

            elif export_type in ['users_sql', 'documents_sql', 'all_sql']:
                # Экспорт в SQL
                with tempfile.NamedTemporaryFile(delete=False, suffix='.sql') as temp_file:
                    backup_file = temp_file.name
                    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                    pg_dump_cmd = [
                        'C:\\Program Files\\PostgreSQL\\17\\bin\\pg_dump.exe',
                        f'--dbname=postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}',
                        '-F', 'p',
                        '--data-only',
                        '--inserts',
                        '--no-owner',
                        '--no-privileges',
                        '--encoding=UTF8'
                    ]
                    if export_type == 'users_sql':
                        pg_dump_cmd.extend(['-t', 'users_user'])
                    elif export_type == 'documents_sql':
                        pg_dump_cmd.extend(['-t', 'docs_document', '-t', 'docs_document_recipients'])
                    pg_dump_cmd.extend(['-f', backup_file])
                    try:
                        result = subprocess.run(pg_dump_cmd, capture_output=True, text=True, check=True, encoding='utf-8')
                        print(f"pg_dump output: {result.stdout}")
                        print(f"pg_dump errors: {result.stderr}")
                        with open(backup_file, 'rb') as f:
                            response = HttpResponse(f.read(), content_type='application/sql')
                            response['Content-Disposition'] = f'attachment; filename="backup_{timestamp}.sql"'
                            def cleanup():
                                if os.path.exists(backup_file):
                                    os.remove(backup_file)
                            atexit.register(cleanup)
                            return response
                    except subprocess.CalledProcessError as e:
                        if os.path.exists(backup_file):
                            os.remove(backup_file)
                        messages.error(request, f'Ошибка экспорта базы данных: {e.stderr}')
                        return redirect('export_import')
                    except Exception as e:
                        if os.path.exists(backup_file):
                            os.remove(backup_file)
                        messages.error(request, f'Неожиданная ошибка при экспорте: {str(e)}')
                        return redirect('export_import')

        # Импорт
        file = request.FILES.get('file')
        if file:
            try:
                file_name = file.name.lower()
                temp_file_path = os.path.join(settings.MEDIA_ROOT, f'temp_import_{file_name}')

                os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

                with open(temp_file_path, 'wb') as f:
                    for chunk in file.chunks():
                        f.write(chunk)

                if file_name.endswith('.sql'):
                    # Чтение SQL файла, удаление BOM
                    with open(temp_file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                        sql_content = f.read()

                    # Исправляем пути
                    sql_content = sql_content.replace('avatars/avatars/', 'avatars/')
                    sql_content = sql_content.replace('media/docs/docs/', 'media/docs/')
                    media_root = settings.MEDIA_ROOT.replace('\\', '\\\\')
                    sql_content = sql_content.replace(f"'{media_root}\\\\", "'").replace(f'"{media_root}\\\\', '"')

                    # Логируем исходный SQL
                    print(f"Original SQL (first 1000 chars):\n{sql_content[:1000]}")

                    # Добавляем ON CONFLICT с помощью regex
                    # Для users_user
                    def replace_users_insert(match):
                        columns = match.group(1)  # Список столбцов
                        values = match.group(2)   # Данные VALUES
                        return (
                            f'INSERT INTO public.users_user {columns} '
                            f'ON CONFLICT (id) DO UPDATE SET '
                            f'email = EXCLUDED.email, '
                            f'full_name = EXCLUDED.full_name, '
                            f'role = EXCLUDED.role, '
                            f'date_joined = EXCLUDED.date_joined, '
                            f'password = EXCLUDED.password, '
                            f'avatar = EXCLUDED.avatar '
                            f'VALUES {values}'
                        )
                    sql_content = re.sub(
                        r'INSERT INTO public\.users_user\s*(\([^)]+\))\s*VALUES\s*(\(.+?\);)',
                        replace_users_insert,
                        sql_content,
                        flags=re.IGNORECASE | re.DOTALL
                    )

                    # Для docs_document
                    def replace_docs_insert(match):
                        columns = match.group(1)
                        values = match.group(2)
                        return (
                            f'INSERT INTO public.docs_document {columns} '
                            f'ON CONFLICT (id) DO UPDATE SET '
                            f'title = EXCLUDED.title, '
                            f'status = EXCLUDED.status, '
                            f'owner_id = EXCLUDED.owner_id, '
                            f'created_at = EXCLUDED.created_at, '
                            f'file = EXCLUDED.file '
                            f'VALUES {values}'
                        )
                    sql_content = re.sub(
                        r'INSERT INTO public\.docs_document\s*(\([^)]+\))\s*VALUES\s*(\(.+?\);)',
                        replace_docs_insert,
                        sql_content,
                        flags=re.IGNORECASE | re.DOTALL
                    )

                    # Для docs_document_recipients
                    def replace_recipients_insert(match):
                        columns = match.group(1)
                        values = match.group(2)
                        return (
                            f'INSERT INTO public.docs_document_recipients {columns} '
                            f'ON CONFLICT (document_id, user_id) DO NOTHING '
                            f'VALUES {values}'
                        )
                    sql_content = re.sub(
                        r'INSERT INTO public\.docs_document_recipients\s*(\([^)]+\))\s*VALUES\s*(\(.+?\);)',
                        replace_recipients_insert,
                        sql_content,
                        flags=re.IGNORECASE | re.DOTALL
                    )

                    # Логируем обработанный SQL
                    print(f"Processed SQL (first 1000 chars):\n{sql_content[:1000]}")

                    # Сохраняем для отладки
                    debug_sql_path = os.path.join(settings.MEDIA_ROOT, f'debug_processed_{file_name}')
                    with open(debug_sql_path, 'w', encoding='utf-8') as f:
                        f.write(sql_content)

                    # Сохраняем обработанный SQL
                    processed_temp_path = os.path.join(settings.MEDIA_ROOT, f'processed_temp_{file_name}')
                    with open(processed_temp_path, 'w', encoding='utf-8') as f:
                        f.write(sql_content)

                    # Выполняем импорт
                    db_settings = settings.DATABASES['default']
                    db_name = db_settings['NAME']
                    db_user = db_settings['USER']
                    db_password = db_settings['PASSWORD']
                    db_host = db_settings['HOST']
                    db_port = db_settings['PORT']
                    psql_cmd = [
                        'C:\\Program Files\\PostgreSQL\\17\\bin\\psql.exe',
                        f'--dbname=postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}',
                        '-f', processed_temp_path
                    ]
                    try:
                        result = subprocess.run(
                            psql_cmd,
                            capture_output=True,
                            text=True,
                            check=True,
                            encoding='cp1251',  # Кодировка для Windows
                            errors='replace'
                        )
                        print(f"psql output: {result.stdout}")
                        print(f"psql errors: {result.stderr}")
                        if "ОШИБКА" in result.stderr or "ERROR" in result.stderr:
                            raise subprocess.CalledProcessError(result.returncode, psql_cmd, output=result.stdout, stderr=result.stderr)
                        os.remove(temp_file_path)
                        os.remove(processed_temp_path)
                        if os.path.exists(debug_sql_path):
                            os.remove(debug_sql_path)
                        messages.success(request, 'База данных успешно импортирована (SQL)')
                        return redirect('export_import')
                    except subprocess.CalledProcessError as e:
                        os.remove(temp_file_path)
                        if os.path.exists(processed_temp_path):
                            os.remove(processed_temp_path)
                        if os.path.exists(debug_sql_path):
                            os.remove(debug_sql_path)
                        messages.error(request, f'Ошибка при импорте SQL: {e.stderr}')
                        return redirect('export_import')
                    except FileNotFoundError as e:
                        os.remove(temp_file_path)
                        if os.path.exists(processed_temp_path):
                            os.remove(processed_temp_path)
                        if os.path.exists(debug_sql_path):
                            os.remove(debug_sql_path)
                        messages.error(request, f'Ошибка: {str(e)}')
                        return redirect('export_import')
                    except Exception as e:
                        os.remove(temp_file_path)
                        if os.path.exists(processed_temp_path):
                            os.remove(processed_temp_path)
                        if os.path.exists(debug_sql_path):
                            os.remove(debug_sql_path)
                        messages.error(request, f'Неожиданная ошибка при импорте: {str(e)}')
                        return redirect('export_import')

                elif file_name.endswith('.csv'):
                    try:
                        with open(temp_file_path, 'rb') as f:
                            file_content = f.read()
                    except IOError as e:
                        os.remove(temp_file_path)
                        messages.error(request, f'Ошибка чтения файла: {str(e)}')
                        return redirect('export_import')

                    try:
                        decoded_file = file_content.decode('utf-8').splitlines()
                        reader = csv.DictReader(decoded_file)
                        headers = reader.fieldnames
                        has_errors = False

                        # Импорт пользователей
                        if 'Email' in headers and 'Full Name' in headers:
                            role_mapping = {'Администратор': 'admin', 'Сотрудник': 'staff', 'admin': 'admin', 'staff': 'staff'}
                            for row in reader:
                                if not row['Email'] or row['Email'] == request.user.email:
                                    continue
                                try:
                                    naive_date = datetime.datetime.strptime(row['Date Joined'], '%Y-%m-%d %H:%M')
                                    aware_date = pytz.UTC.localize(naive_date)
                                    role = role_mapping.get(row['Role'], 'staff')
                                    avatar_path = row.get('Avatar Path', '').strip()
                                    full_avatar_path = os.path.join(settings.MEDIA_ROOT, avatar_path) if avatar_path else ''
                                    user, created = User.objects.get_or_create(
                                        email=row['Email'],
                                        defaults={
                                            'id': row.get('ID'),
                                            'full_name': row['Full Name'],
                                            'role': role,
                                            'date_joined': aware_date,
                                            'password': row.get('Password', '') if 'Password' in headers else ''
                                        }
                                    )
                                    if not created:
                                        user.full_name = row['Full Name']
                                        user.role = role
                                        user.date_joined = aware_date
                                        if 'Password' in headers and row['Password']:
                                            user.password = row['Password']
                                    if avatar_path and os.path.exists(full_avatar_path):
                                        user.avatar.name = avatar_path
                                    else:
                                        user.avatar = None
                                    user.save()
                                except (IntegrityError, ValueError) as e:
                                    has_errors = True
                                    messages.error(request, f'Ошибка при импорте пользователя {row["Email"]}: {str(e)}')
                                    continue

                        # Импорт документов
                        elif 'Title' in headers and 'Status' in headers:
                            status_mapping = {'Черновик': 'draft', 'Отправлен': 'sent', 'Подписан': 'signed',
                                             'draft': 'draft', 'sent': 'sent', 'signed': 'signed'}
                            for row in reader:
                                doc_id = row.get('ID', '').strip().lstrip('\ufeff')
                                if not doc_id or not row.get('Title'):
                                    has_errors = True
                                    continue
                                owner = User.objects.filter(email=row['Owner']).first() if row.get('Owner') else None
                                if not owner:
                                    has_errors = True
                                    continue
                                recipients_emails = row['Recipients'].split(', ') if row.get('Recipients') else []
                                recipients = User.objects.filter(email__in=recipients_emails)
                                try:
                                    created_at_str = row['Created At']
                                    try:
                                        naive_date = datetime.datetime.strptime(created_at_str, '%Y-%m-%d %H:%M')
                                    except ValueError:
                                        naive_date = datetime.datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                                    aware_date = pytz.UTC.localize(naive_date)
                                    status = status_mapping.get(row['Status'], 'draft')
                                    doc, created = Document.objects.get_or_create(
                                        id=doc_id,
                                        defaults={
                                            'title': row['Title'],
                                            'status': status,
                                            'owner': owner,
                                            'created_at': aware_date,
                                        }
                                    )
                                    if not created:
                                        doc.title = row['Title']
                                        doc.status = status
                                        doc.owner = owner
                                        doc.created_at = aware_date
                                    file_path = row.get('File Path', '').strip()
                                    full_file_path = os.path.join(settings.MEDIA_ROOT, file_path) if file_path else ''
                                    if file_path and os.path.exists(full_file_path):
                                        doc.file.name = file_path
                                    else:
                                        doc.file.save(f'dummy_{doc_id}.txt', ContentFile(b''))
                                    doc.save()
                                    doc.recipients.set(recipients)
                                except (IntegrityError, ValueError) as e:
                                    has_errors = True
                                    messages.error(request, f'Ошибка при импорте документа {doc_id}: {str(e)}')
                                    continue

                        else:
                            os.remove(temp_file_path)
                            messages.error(request, 'Неизвестный формат CSV: некорректные заголовки')
                            return redirect('export_import')

                        os.remove(temp_file_path)
                        if has_errors:
                            messages.error(request, 'Произошли ошибки при импорте данных, проверьте логи')
                        else:
                            messages.success(request, 'Данные успешно импортированы')
                        return redirect('export_import')

                    except UnicodeDecodeError:
                        os.remove(temp_file_path)
                        messages.error(request, 'Ошибка декодирования файла: файл должен быть в формате UTF-8')
                        return redirect('export_import')

                else:
                    os.remove(temp_file_path)
                    messages.error(request, 'Неподдерживаемый формат файла. Используйте .csv или .sql')
                    return redirect('export_import')

            except Exception as e:
                if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except OSError as remove_error:
                        import time
                        time.sleep(0.5)
                        try:
                            os.remove(temp_file_path)
                        except OSError:
                            messages.error(request, f'Не удалось удалить временный файл: {str(remove_error)}')
                messages.error(request, f'Ошибка импорта: {str(e)}')
                return redirect('export_import')

    return render(request, 'users/export_import.html')

def password_reset_request(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                token = PasswordResetToken.objects.create(user=user)
                reset_url = request.build_absolute_uri(
                    reverse('password_reset_confirm', args=[str(token.token)])
                )
                send_mail(
                    subject='Сброс пароля в EDMS',
                    message=(
                        f'Здравствуйте, {user.full_name}!\n\n'
                        f'Вы запросили сброс пароля для вашего аккаунта в EDMS.\n'
                        f'Перейдите по следующей ссылке, чтобы установить новый пароль:\n'
                        f'{reset_url}\n\n'
                        f'Если вы не запрашивали сброс пароля, проигнорируйте это письмо.\n'
                        f'Ссылка действительна в течение 1 часа.'
                    ),
                    from_email='dsistema@internet.ru',
                    recipient_list=[email],
                )
                messages.success(request, 'Письмо для сброса пароля отправлено на ваш email.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь с таким email не найден.')
    else:
        form = PasswordResetRequestForm()
    return render(request, 'users/password_reset_request.html', {'form': form})

def password_reset_confirm(request, token):
    token_obj = get_object_or_404(PasswordResetToken, token=token)
    if not token_obj.is_valid():
        messages.error(request, 'Ссылка недействительна или истёк срок действия.')
        return redirect('login')

    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            token_obj.user.set_password(form.cleaned_data['password'])
            token_obj.user.save()
            token_obj.delete()
            messages.success(request, 'Пароль успешно изменён. Теперь вы можете войти.')
            return redirect('login')
    else:
        form = PasswordResetForm()
    return render(request, 'users/password_reset_confirm.html', {'form': form})

@admin_required
def toggle_email_notifications(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.email_notifications = not user.email_notifications
    user.save()
    status = 'включены' if user.email_notifications else 'отключены'
    messages.success(request, f'Уведомления для {user.full_name} {status}')
    print(f"Email notifications {status} for {user.email} by admin {request.user.email}")
    return redirect('user_list')