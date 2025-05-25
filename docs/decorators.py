from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from functools import wraps
from .views import error_403  # Импортируем error_403

def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'admin':
            return error_403(request)  # Используем кастомный обработчик
        return view_func(request, *args, **kwargs)
    return wrapper