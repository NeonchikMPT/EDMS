from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from docs.decorators import admin_required
from docs.models import Document, Notification, DocumentLog
from users.models import User
from datetime import datetime, time
from django.utils import timezone

@login_required
def dashboard(request):
    # Текущая статистика
    incoming_count = Document.objects.filter(recipients__in=[request.user]).count()  # Все входящие
    sent_count = Document.objects.filter(owner=request.user).count()
    signed_count = Document.objects.filter(recipients__in=[request.user], status='signed').count()

    # Последние уведомления о новых документах
    recent_notifs = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')[:5]

    # Уведомления о новых комментариях (для документов, где пользователь — owner)
    comment_logs = DocumentLog.objects.filter(
        document__owner=request.user,
        action='comment',
        timestamp__gt=request.user.last_login  # Только новые комментарии
    ).order_by('-timestamp')[:5]

    # Данные для графика
    if request.user.role == 'admin':
        statuses = ['draft', 'sent', 'signed']
        status_counts = [Document.objects.filter(status=status).count() for status in statuses]
        chart_data = {
            'labels': ['Черновик', 'Отправлен', 'Подписан'],
            'data': status_counts,
            'colors': ['#FFCE56', '#4BC0C0', '#9966FF']
        }
    else:
        chart_data = {
            'labels': ['Входящие', 'Подписанные'],
            'data': [incoming_count, signed_count],
            'colors': ['#36A2EB', '#FF6384']
        }

    return render(request, 'dashboard.html', {
        'incoming_count': incoming_count,
        'sent_count': sent_count,
        'signed_count': signed_count,
        'recent_notifs': recent_notifs,
        'comment_logs': comment_logs,
        'chart_data': chart_data
    })

@admin_required
def logs(request):
    logs = DocumentLog.objects.all().order_by('-timestamp')
    users = User.objects.all()
    actions = DocumentLog.ACTION_CHOICES

    # Фильтры
    user_filter = request.GET.get('user')
    action_filter = request.GET.get('action')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if user_filter:
        logs = logs.filter(user__id=user_filter)
    if action_filter:
        logs = logs.filter(action=action_filter)
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d')
            date_from = timezone.make_aware(datetime.combine(date_from, time.min))
            logs = logs.filter(timestamp__gte=date_from)
        except ValueError:
            pass  # Игнорируем некорректную дату
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d')
            date_to = timezone.make_aware(datetime.combine(date_to, time.max))
            logs = logs.filter(timestamp__lte=date_to)
        except ValueError:
            pass  # Игнорируем некорректную дату

    return render(request, 'logs.html', {
        'logs': logs,
        'users': users,
        'actions': actions,
        'selected_user': user_filter,
        'selected_action': action_filter,
        'selected_date_from': date_from,
        'selected_date_to': date_to
    })

def help_view(request):
    return render(request, 'help.html')