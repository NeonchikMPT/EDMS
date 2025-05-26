from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import timezone
import logging
import json
from .models import Document, Notification, DocumentLog, Signature
from .forms import DocumentForm
from users.models import User

logger = logging.getLogger(__name__)

@login_required
def search_users(request):
    query = request.GET.get('q', '')
    doc_id = request.GET.get('doc_id')
    if len(query) < 3 and not doc_id:
        return JsonResponse({'users': []})

    if len(query) < 3 and doc_id:
        doc = get_object_or_404(Document, id=doc_id)
        users = [{'id': r.id, 'email': r.email, 'full_name': r.full_name, 'selected': True} for r in
                 doc.recipients.all()]
        return JsonResponse({'users': users})

    users = User.objects.filter(email__icontains=query).values('id', 'email', 'full_name')[:10]
    return JsonResponse({'users': list(users)})

@login_required
def my_documents(request):
    if request.user.role == 'admin':
        docs = Document.objects.all()
    else:
        docs = Document.objects.filter(owner=request.user)

    title_filter = request.GET.get('title', '')
    status_filter = request.GET.get('status', '')
    recipient_filter = request.GET.get('recipient', '')

    if title_filter:
        docs = docs.filter(title__icontains=title_filter)
    if status_filter:
        docs = docs.filter(status=status_filter)
    if recipient_filter:
        docs = docs.filter(recipients__full_name__icontains=recipient_filter)

    docs = docs.order_by('-created_at')

    return render(request, 'docs/my_documents.html', {
        'docs': docs,
        'title_filter': title_filter,
        'status_filter': status_filter,
        'recipient_filter': recipient_filter,
    })

@login_required
def document_create(request):
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.owner = request.user
            doc.save()
            recipients = form.cleaned_data['recipients']
            if recipients:
                doc.recipients.set(recipients)
                doc.status = 'sent'
                for recipient in recipients:
                    Signature.objects.get_or_create(document=doc, user=recipient)
                messages.success(request, 'Документ успешно создан и отправлен на подпись.')
            else:
                doc.status = 'draft'
                messages.warning(request, 'Документ создан и сохранен как черновик. Выберите получателей для отправки на подпись.')
            doc.save()

            DocumentLog.objects.create(
                document=doc,
                user=request.user,
                action='create',
                comment='Создан документ'
            )
            logger.info(f"Document created: {doc.title} by {request.user.email}")

            for recipient in recipients:
                Notification.objects.create(user=recipient, document=doc)
                logger.info(f"Notification created for {recipient.email}")
                if recipient.email_notifications:
                    try:
                        send_mail(
                            subject='Новый документ в EDMS',
                            message=(
                                f'Здравствуйте, {recipient.full_name}!\n\n'
                                f'Вам отправлен новый документ: "{doc.title}".\n'
                                f'Проверьте его в разделе "Входящие".'
                            ),
                            from_email='dsistema@internet.ru',
                            recipient_list=[recipient.email],
                        )
                        logger.info(f"Email sent to {recipient.email}")
                    except Exception as e:
                        logger.error(f"Error sending email to {recipient.email}: {str(e)}")

            return redirect('my_documents')
    else:
        form = DocumentForm()
    return render(request, 'docs/document_form.html', {'form': form})

@login_required
def document_edit(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)
    if request.user != doc.owner and request.user.role != 'admin':
        return error_403(request)

    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, instance=doc)
        if form.is_valid():
            doc = form.save(commit=False)
            old_recipients = set(doc.recipients.all())
            new_recipients = set(form.cleaned_data['recipients'])
            doc.save()
            doc.recipients.set(new_recipients)

            for recipient in new_recipients - old_recipients:
                Signature.objects.get_or_create(document=doc, user=recipient)
                Notification.objects.create(user=recipient, document=doc)
                if recipient.email_notifications:
                    try:
                        send_mail(
                            subject='Обновление документа в EDMS',
                            message=(
                                f'Здравствуйте, {recipient.full_name}!\n\n'
                                f'Документ "{doc.title}" обновлен и требует вашей подписи.\n'
                                f'Проверьте его в разделе "Входящие".'
                            ),
                            from_email='dsistema@internet.ru',
                            recipient_list=[recipient.email],
                        )
                        logger.info(f"Email sent to {recipient.email}")
                    except Exception as e:
                        logger.error(f"Error sending email to {recipient.email}: {str(e)}")
                for recipient in old_recipients - new_recipients:
                    Signature.objects.filter(document=doc, user_id=recipient.id).delete()

            if new_recipients:
                doc.status = 'sent'
                messages.success(request, 'Документ успешно отредактирован и отправлен на подпись.')
            else:
                doc.status = 'draft'
                messages.warning(request, 'Документ отредактирован и сохранен как черновик. Выберите получателей для отправки на подпись.')
            doc.save()

            DocumentLog.objects.create(
                document=doc,
                user=request.user,
                action='edit',
                comment='Документ отредактирован'
            )
            logger.info(f"Document edited: {doc.title} by {request.user.email}")
            return redirect('my_documents')
    else:
        form = DocumentForm(instance=doc)
    return render(request, 'docs/document_edit.html', {'form': form, 'doc': doc})

@login_required
def document_delete(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)
    if request.user != doc.owner and request.user.role != 'admin':
        return error_403(request)

    if request.method == 'POST':
        # Log the deletion
        DocumentLog.objects.create(
            document=doc,
            user=request.user,
            action='delete',
            comment='Документ удален'
        )
        logger.info(f"Document deleted: {doc.title} by {request.user.email}")

        # Delete associated file from storage
        if doc.file:
            doc.file.delete(save=False)

        # Delete the document (cascades to signatures, notifications, logs)
        doc.delete()

        messages.success(request, 'Документ успешно удален.')
        return redirect('my_documents')

    return redirect('document_edit', doc_id=doc.id)

@login_required
def document_sign(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)
    if request.user != doc.owner and request.user not in doc.recipients.all() and request.user.role != 'admin':
        return error_403(request)

    signature, created = Signature.objects.get_or_create(document=doc, user=request.user)
    if not created and signature.signed_at:
        messages.error(request, 'Вы уже подписали этот документ.')
        return redirect('document_view', doc_id=doc.id)

    if request.method == 'POST':
        signature.signed_at = timezone.now()
        signature.save()
        doc.status = 'signed' if all(s.signed_at for s in doc.signatures.all()) else 'sent'
        doc.save()

        DocumentLog.objects.create(
            document=doc,
            user=request.user,
            action='sign',
            comment='Документ подписан'
        )
        logger.info(f"Document signed: {doc.title} by {request.user.email}")
        return JsonResponse({'status': 'success'})

    return redirect('document_view', doc_id=doc.id)

@login_required
def document_view(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)
    if doc.owner != request.user and not doc.recipients.filter(id=request.user.id).exists() and request.user.role != 'admin':
        return error_403(request)
    logs = DocumentLog.objects.filter(document=doc, action='comment').order_by('-timestamp')
    can_edit = request.user == doc.owner or request.user.role == 'admin'
    return render(request, 'docs/document_view.html', {'document': doc, 'comments': logs, 'can_edit': can_edit})

@login_required
def add_comment(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id, recipients__in=[request.user])
    if request.method == 'POST':
        data = json.loads(request.body)
        comment = data.get('comment')
        if not comment:
            return JsonResponse({'status': 'error', 'message': 'Комментарий не может быть пустым'})

        DocumentLog.objects.create(
            document=doc,
            user=request.user,
            action='comment',
            comment=comment
        )

        Notification.objects.create(
            user=doc.owner,
            document=doc,
            is_read=False
        )
        if doc.owner.email_notifications:
            try:
                send_mail(
                    subject='Новый комментарий к вашему документу в EDMS',
                    message=(
                        f'Здравствуйте, {doc.owner.full_name}!\n\n'
                        f'Пользователь {request.user.full_name} оставил комментарий к вашему документу "{doc.title}":\n'
                        f'"{comment}"\n'
                        f'Проверьте его в разделе "Мои документы".'
                    ),
                    from_email='dsistema@internet.ru',
                    recipient_list=[doc.owner.email],
                )
                logger.info(f"Email sent to {doc.owner.email}")
            except Exception as e:
                logger.error(f"Error sending email to {doc.owner.email}: {str(e)}")

        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Недопустимый метод запроса'})

@login_required
def received_documents(request):
    docs = Document.objects.filter(recipients__in=[request.user]).order_by('-created_at')
    return render(request, 'docs/received_documents.html', {'docs': docs})

@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'docs/notifications.html', {'notifications': notifications})

@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    logger.info(f"Notification marked as read: {notification.document.title} for {request.user.email}")
    return JsonResponse({'status': 'success'})

@login_required
def document_logs(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)
    logs = doc.logs.order_by('-timestamp')
    return render(request, 'docs/document_logs.html', {'doc': doc, 'logs': logs})

@login_required
def check_notifications(request):
    notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    latest_notification = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at').first()
    data = {
        'count': notifications,
        'latest': {
            'id': latest_notification.id,
            'title': latest_notification.document.title,
            'created_at': latest_notification.created_at.strftime('%d.%m.%Y %H:%M'),
        } if latest_notification else None
    }
    return JsonResponse(data)

def error_403(request, exception=None):
    return render(request, 'error.html', {
        'error_code': 403,
        'error_title': 'Отказано в доступе',
        'error_message': 'У вас нет прав для доступа к этой странице.'
    }, status=403)

def error_404(request, exception=None):
    return render(request, 'error.html', {
        'error_code': 404,
        'error_title': 'Страница не найдена',
        'error_message': 'К сожалению, запрашиваемая страница не существует.'
    }, status=404)

def error_500(request, exception=None):
    return render(request, 'error.html', {
        'error_code': 500,
        'error_title': 'Внутренняя ошибка сервера',
        'error_message': 'Что-то пошло не так. Мы уже работаем над этим.'
    }, status=500)

def error_400(request, exception=None):
    return render(request, 'error.html', {
        'error_code': 400,
        'error_title': 'Неверный запрос',
        'error_message': 'Сервер не смог обработать ваш запрос из-за ошибки в данных.'
    }, status=400)