from django.db import models
from users.models import User

class Document(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('sent', 'Отправлен'),
        ('signed', 'Подписан'),
    ]

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='docs/')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_docs')
    recipients = models.ManyToManyField(User, related_name='received_docs', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Signature(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='signatures')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('document', 'user')  # Один пользователь подписывает документ только раз

    def __str__(self):
        return f'Подпись {self.user.email} для {self.document.title}'

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('new_document', 'Новый документ'),
        ('new_comment', 'Новый комментарий'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='new_document')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Уведомление для {self.user.email} по документу "{self.document.title}"'

class DocumentLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Создание'),
        ('edit', 'Редактирование'),
        ('sign', 'Подписание'),
        ('comment', 'Комментарий'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)

    def __str__(self):
        return f'{self.user.email} — {self.get_action_display()} — {self.timestamp}'