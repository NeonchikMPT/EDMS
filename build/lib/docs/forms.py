from django import forms
from .models import Document
from users.models import User

class DocumentForm(forms.ModelForm):
    recipients = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Document
        fields = ['title', 'file', 'recipients']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите название документа'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'title': 'Название',
            'file': 'Файл',
        }

    def clean_recipients(self):
        recipients_data = self.cleaned_data['recipients']
        if not recipients_data:
            return []
        try:
            recipient_ids = [int(id) for id in recipients_data.split(',')]
            return User.objects.filter(id__in=recipient_ids)
        except (ValueError, TypeError):
            raise forms.ValidationError("Некорректный формат подписантов")