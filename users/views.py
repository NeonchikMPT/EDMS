import random
import re
import string
import subprocess
from django.urls import reverse
from datetime import datetime
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

from docs.decorators import admin_required
from docs.views import error_403
from .forms import RegisterForm, ProfileForm, LoginForm, PasswordResetRequestForm, PasswordResetForm, UserProfileForm
from .models import User, PasswordResetToken
from docs.models import Document


def generate_temp_password(length=8):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

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
    if request.user.role != 'admin' and request.user != user:  # Проверка прав
        return error_403(request)
    if request.method == 'POST':
        # Обработка удаления аватара
        if 'delete_avatar' in request.POST:
            if user.avatar:
                user.avatar.delete()  # Удаляет файл с диска
            user.avatar = None
            user.save()
            messages.success(request, 'Аватар удалён.')
            return redirect('user_edit', user_id=user.id)

        # Обработка редактирования пользователя
        try:
            # Проверка паролей
            new_password = request.POST.get('new_password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()
            if new_password or confirm_password:
                if new_password != confirm_password:
                    messages.error(request, 'Пароли не совпадают.')
                    return render(request, 'users/user_edit.html', {'user': user})
                if len(new_password) < 8:
                    messages.error(request, 'Пароль должен содержать минимум 8 символов.')
                    return render(request, 'users/user_edit.html', {'user': user})
                user.set_password(new_password)

            # Обновление остальных полей
            user.full_name = request.POST.get('full_name', '').strip()
            user.email_notifications = 'email_notifications' in request.POST
            if request.user.role == 'admin':  # Только админ может менять роль
                user.role = request.POST.get('role', 'staff')

            # Обработка загрузки аватара
            if 'avatar' in request.FILES:
                user.avatar = request.FILES['avatar']

            user.save()

            # Если редактируемый пользователь — это текущий пользователь, обновляем сессию
            if user == request.user and new_password:
                user = authenticate(request, username=user.email, password=new_password)
                if user:
                    login(request, user)  # Обновляем сессию
                    messages.success(request, 'Пользователь успешно обновлён.')
                else:
                    messages.error(request, 'Ошибка при обновлении сессии после смены пароля.')
            else:
                messages.success(request, 'Пользователь успешно обновлён.')

            return redirect('user_edit', user_id=user.id)
        except Exception as e:
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
        # Обработка удаления аватара
        if 'delete_avatar' in request.POST:
            if request.user.avatar:
                request.user.avatar.delete()  # Удаляем файл аватара
                request.user.avatar = None
                request.user.save()
                messages.success(request, 'Аватар удалён')
                return redirect('profile')

        # Обработка обновления профиля
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            new_password = form.cleaned_data.get('new_password')
            if new_password:
                user.set_password(new_password)
            user.save()
            print(f"Profile updated for {user.email}, email_notifications: {user.email_notifications}")

            # Аутентификация пользователя заново с новым паролем
            user = authenticate(request, username=user.email, password=new_password)
            if user:
                login(request, user)  # Обновляем сессию
                messages.success(request, 'Профиль обновлён')
            else:
                messages.error(request, 'Ошибка при обновлении сессии после смены пароля')
            return redirect('profile')
        else:
            print(f"Form validation failed for {request.user.email}: {form.errors}")
            messages.error(request, 'Ошибка при обновлении профиля: проверьте введённые данные')
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'users/profile.html', {'form': form})

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
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
    if request.method == 'POST':
        export_type = request.POST.get('export_type')
        # Экспорт CSV
        if export_type == 'users_csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = 'attachment; filename="users.csv"'
            writer = csv.writer(response)
            writer.writerow(['ID', 'Email', 'Full Name', 'Role', 'Date Joined', 'Temp Password'])
            users = User.objects.all()
            for user in users:
                temp_password = generate_temp_password()
                writer.writerow([
                    user.id,
                    user.email,
                    user.full_name,
                    user.role,
                    user.date_joined.strftime('%Y-%m-%d %H:%M'),
                    temp_password
                ])
            return response
        elif export_type == 'documents_csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = 'attachment; filename="documents.csv"'
            writer = csv.writer(response)
            writer.writerow(['ID', 'Title', 'Status', 'Owner', 'Recipient', 'Created At'])
            documents = Document.objects.all()
            for doc in documents:
                writer.writerow([
                    doc.id,
                    doc.title,
                    doc.status,
                    doc.owner.email if doc.owner else '',
                    doc.recipient.email if doc.recipient else '',
                    doc.created_at.strftime('%Y-%m-%d %H:%M')
                ])
            return response
        # Экспорт SQL
        elif export_type == 'users_sql':
            response = HttpResponse(content_type='text/sql')
            response['Content-Disposition'] = 'attachment; filename="users.sql"'
            output = StringIO()
            users = User.objects.all()
            for user in users:
                temp_password = generate_temp_password()
                output.write(
                    f"INSERT INTO users_user (id, email, full_name, role, date_joined, password) VALUES ({user.id}, '{user.email}', '{user.full_name}', '{user.role}', '{user.date_joined.strftime('%Y-%m-%d %H:%M:%S')}', '{temp_password}');\n")
            response.write(output.getvalue())
            output.close()
            return response
        elif export_type == 'documents_sql':
            response = HttpResponse(content_type='text/sql')
            response['Content-Disposition'] = 'attachment; filename="documents.sql"'
            output = StringIO()
            documents = Document.objects.all()
            for doc in documents:
                owner_id = f"'{doc.owner.id}'" if doc.owner else 'NULL'
                recipient_id = f"'{doc.recipient.id}'" if doc.recipient else 'NULL'
                output.write(
                    f"INSERT INTO docs_document (id, title, status, owner_id, recipient_id, created_at) VALUES ({doc.id}, '{doc.title}', '{doc.status}', {owner_id}, {recipient_id}, '{doc.created_at.strftime('%Y-%m-%d %H:%M:%S')}');\n")
            response.write(output.getvalue())
            output.close()
            return response
        elif export_type == 'all_sql':
            db_settings = settings.DATABASES['default']
            db_name = db_settings['NAME']
            db_user = db_settings['USER']
            db_password = db_settings['PASSWORD']
            db_host = db_settings['HOST']
            db_port = db_settings['PORT']
            pg_dump_cmd = [
                'pg_dump',
                f'--dbname=postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}',
                '--format=plain',
                '--no-owner',
                '--no-privileges'
            ]
            try:
                result = subprocess.run(pg_dump_cmd, capture_output=True, text=True, check=True)
                response = HttpResponse(content_type='text/sql')
                response['Content-Disposition'] = 'attachment; filename="database.sql"'
                response.write(result.stdout)
                return response
            except subprocess.CalledProcessError as e:
                messages.error(request, f'Ошибка экспорта базы данных: {e.stderr}')
                return redirect('export_import')
            except FileNotFoundError:
                messages.error(request,
                               'Утилита pg_dump не найдена. Убедитесь, что PostgreSQL установлен и pg_dump доступен в PATH.')
                return redirect('export_import')
        # Импорт CSV
        elif export_type == 'import_users_csv':
            csv_file = request.FILES.get('csv_file')
            if csv_file:
                try:
                    decoded_file = csv_file.read().decode('utf-8').splitlines()
                    reader = csv.DictReader(decoded_file)
                    role_mapping = {'Администратор': 'admin', 'Сотрудник': 'staff', 'admin': 'admin', 'staff': 'staff'}
                    for row in reader:
                        if row['Email'] == request.user.email:
                            continue
                        naive_date = datetime.strptime(row['Date Joined'], '%Y-%m-%d %H:%M')
                        aware_date = pytz.UTC.localize(naive_date)
                        role = role_mapping.get(row['Role'], 'staff')
                        user, created = User.objects.get_or_create(
                            email=row['Email'],
                            defaults={
                                'full_name': row['Full Name'],
                                'role': role,
                                'date_joined': aware_date
                            }
                        )
                        if not created:
                            user.full_name = row['Full Name']
                            user.role = role
                            user.date_joined = aware_date
                        if 'Temp Password' in row and row['Temp Password']:
                            user.set_password(row['Temp Password'])
                        user.save()
                    messages.success(request, 'Пользователи импортированы (CSV)')
                except Exception as e:
                    messages.error(request, f'Ошибка импорта: {str(e)}')
                return redirect('export_import')
        elif export_type == 'import_documents_csv':
            csv_file = request.FILES.get('csv_file')
            if csv_file:
                try:
                    decoded_file = csv_file.read().decode('utf-8').splitlines()
                    reader = csv.DictReader(decoded_file)
                    status_mapping = {'Черновик': 'draft', 'Отправлен': 'sent', 'Подписан': 'signed', 'draft': 'draft',
                                      'sent': 'sent', 'signed': 'signed'}
                    for row in reader:
                        owner = User.objects.filter(email=row['Owner']).first()
                        recipient = User.objects.filter(email=row['Recipient']).first()
                        naive_date = datetime.strptime(row['Created At'], '%Y-%m-%d %H:%M')
                        aware_date = pytz.UTC.localize(naive_date)
                        status = status_mapping.get(row['Status'], 'draft')
                        doc, created = Document.objects.get_or_create(
                            id=row['ID'],
                            defaults={
                                'title': row['Title'],
                                'status': status,
                                'owner': owner,
                                'recipient': recipient,
                                'created_at': aware_date
                            }
                        )
                        if not created:
                            doc.title = row['Title']
                            doc.status = status
                            doc.owner = owner
                            doc.recipient = recipient
                            doc.created_at = aware_date
                        doc.save()
                    messages.success(request, 'Документы импортированы (CSV)')
                except Exception as e:
                    messages.error(request, f'Ошибка импорта: {str(e)}')
                return redirect('export_import')
        # Импорт SQL
        elif export_type == 'import_users_sql':
            sql_file = request.FILES.get('sql_file')
            if sql_file:
                try:
                    db_settings = settings.DATABASES['default']
                    conn = psycopg2.connect(
                        dbname=db_settings['NAME'],
                        user=db_settings['USER'],
                        password=db_settings['PASSWORD'],
                        host=db_settings['HOST'],
                        port=db_settings['PORT']
                    )
                    cursor = conn.cursor()
                    sql_content = sql_file.read().decode('utf-8')
                    sql_commands = sql_content.split(';')
                    role_mapping = {'Администратор': 'admin', 'Сотрудник': 'staff', 'admin': 'admin', 'staff': 'staff'}
                    for command in sql_commands:
                        command = command.strip()
                        if command and 'INSERT INTO users_user' in command:
                            match = re.match(r"INSERT INTO users_user \((.*?)\) VALUES \((.*?)\)", command)
                            if match:
                                columns = [col.strip() for col in match.group(1).split(',')]
                                values = [val.strip().strip("'") for val in match.group(2).split(',')]
                                email = values[columns.index('email')]
                                if email == request.user.email:
                                    continue
                                naive_date = datetime.strptime(values[columns.index('date_joined')],
                                                               '%Y-%m-%d %H:%M:%S')
                                aware_date = pytz.UTC.localize(naive_date)
                                role = role_mapping.get(values[columns.index('role')], 'staff')
                                cursor.execute("SELECT 1 FROM users_user WHERE email = %s", (email,))
                                if cursor.fetchone():
                                    update_query = """
                                    UPDATE users_user
                                    SET full_name = %s, role = %s, date_joined = %s
                                    WHERE email = %s
                                    """
                                    cursor.execute(update_query, (
                                        values[columns.index('full_name')],
                                        role,
                                        aware_date,
                                        email
                                    ))
                                else:
                                    values[columns.index('role')] = role
                                    modified_values = ', '.join(f"'{val}'" if val else 'NULL' for val in values)
                                    modified_command = f"INSERT INTO users_user ({match.group(1)}) VALUES ({modified_values})"
                                    cursor.execute(modified_command)
                                if 'password' in columns and values[columns.index('password')]:
                                    cursor.execute("UPDATE users_user SET password = %s WHERE email = %s", (
                                        User.objects.make_password(values[columns.index('password')]),
                                        email
                                    ))
                    conn.commit()
                    conn.close()
                    messages.success(request, 'Пользователи импортированы (SQL)')
                except Exception as e:
                    messages.error(request, f'Ошибка импорта: {str(e)}')
                return redirect('export_import')
        elif export_type == 'import_documents_sql':
            sql_file = request.FILES.get('sql_file')
            if sql_file:
                try:
                    db_settings = settings.DATABASES['default']
                    conn = psycopg2.connect(
                        dbname=db_settings['NAME'],
                        user=db_settings['USER'],
                        password=db_settings['PASSWORD'],
                        host=db_settings['HOST'],
                        port=db_settings['PORT']
                    )
                    cursor = conn.cursor()
                    sql_content = sql_file.read().decode('utf-8')
                    sql_commands = sql_content.split(';')
                    status_mapping = {'Черновик': 'draft', 'Отправлен': 'sent', 'Подписан': 'signed', 'draft': 'draft',
                                      'sent': 'sent', 'signed': 'signed'}
                    for command in sql_commands:
                        command = command.strip()
                        if command and 'INSERT INTO docs_document' in command:
                            match = re.match(r"INSERT INTO docs_document \((.*?)\) VALUES \((.*?)\)", command)
                            if match:
                                columns = [col.strip() for col in match.group(1).split(',')]
                                values = [val.strip().strip("'") if val != 'NULL' else None for val in
                                          match.group(2).split(',')]
                                doc_id = values[columns.index('id')]
                                naive_date = datetime.strptime(values[columns.index('created_at')],
                                                               '%Y-%m-%d %H:%M:%S')
                                aware_date = pytz.UTC.localize(naive_date)
                                status = status_mapping.get(values[columns.index('status')], 'draft')
                                cursor.execute("SELECT 1 FROM docs_document WHERE id = %s", (doc_id,))
                                if cursor.fetchone():
                                    update_query = """
                                    UPDATE docs_document
                                    SET title = %s, status = %s, owner_id = %s, recipient_id = %s, created_at = %s
                                    WHERE id = %s
                                    """
                                    cursor.execute(update_query, (
                                        values[columns.index('title')],
                                        status,
                                        values[columns.index('owner_id')],
                                        values[columns.index('recipient_id')],
                                        aware_date,
                                        doc_id
                                    ))
                                else:
                                    values[columns.index('status')] = status
                                    modified_values = ', '.join(f"'{val}'" if val else 'NULL' for val in values)
                                    modified_command = f"INSERT INTO docs_document ({match.group(1)}) VALUES ({modified_values})"
                                    cursor.execute(modified_command)
                    conn.commit()
                    conn.close()
                    messages.success(request, 'Документы импортированы (SQL)')
                except Exception as e:
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