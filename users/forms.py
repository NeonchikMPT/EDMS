from django import forms
from .models import User, PasswordResetToken

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Пароль")

    class Meta:
        model = User
        fields = ['email', 'full_name', 'password']
        labels = {
            'email': 'Email',
            'full_name': 'ФИО',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Пользователь с таким email уже существует.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'staff'  # Устанавливаем роль 'staff' для самостоятельной регистрации
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    email = forms.EmailField(label='Email')
    password = forms.CharField(widget=forms.PasswordInput, label='Пароль')

class ProfileForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Пароль", required=False)  # Добавлено поле для создания
    new_password = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput,
        required=False
    )
    confirm_password = forms.CharField(
        label='Подтвердите новый пароль',
        widget=forms.PasswordInput,
        required=False
    )

    class Meta:
        model = User
        fields = ['email', 'full_name', 'avatar', 'role', 'password', 'new_password', 'confirm_password']
        labels = {
            'email': 'Email',
            'full_name': 'Полное имя',
            'avatar': 'Аватар',
            'role': 'Роль',
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        # Валидация для создания нового пользователя
        if not self.instance.id and not password:  # Новый пользователь
            raise forms.ValidationError('Пароль обязателен для нового пользователя.')
        if password and len(password) < 8:
            raise forms.ValidationError('Пароль должен содержать минимум 8 символов.')

        # Валидация для изменения пароля
        if new_password or confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError('Пароли не совпадают')
            if new_password and len(new_password) < 8:
                raise forms.ValidationError('Пароль должен содержать не менее 8 символов')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password') or self.cleaned_data.get('new_password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user

class UserProfileForm(forms.ModelForm):
    new_password = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput,
        required=False
    )
    confirm_password = forms.CharField(
        label='Подтвердите новый пароль',
        widget=forms.PasswordInput,
        required=False
    )

    class Meta:
        model = User
        fields = ['email', 'full_name', 'avatar', 'email_notifications', 'new_password', 'confirm_password']
        widgets = {
            'email_notifications': forms.CheckboxInput(),
        }
        labels = {
            'email': 'Email',
            'full_name': 'Полное имя',
            'avatar': 'Аватар',
            'email_notifications': 'Получать уведомления на email',
        }

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        email = cleaned_data.get('email')

        if email and email != self.instance.email:
            if User.objects.filter(email=email).exclude(id=self.instance.id).exists():
                raise forms.ValidationError('Пользователь с таким email уже существует.')

        if new_password or confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError('Пароли не совпадают')
            if new_password and len(new_password) < 8:
                raise forms.ValidationError('Пароль должен содержать не менее 8 символов')
        return cleaned_data

class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(label='Email')

class PasswordResetForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label='Новый пароль')
    confirm_password = forms.CharField(widget=forms.PasswordInput, label='Подтвердите новый пароль')

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Пароли не совпадают")
        return cleaned_data