from django.contrib import admin
from django.urls import path, include

from . import views
from .views import dashboard  # вместо index_redirect

from django.conf import settings
from django.conf.urls.static import static

from docs.views import error_400, error_403, error_404, error_500

handler400 = error_400
handler403 = error_403
handler404 = error_404
handler500 = error_500

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('docs/', include('docs.urls')),
    path('logs/', views.logs, name='logs'),
    path('help/', views.help_view, name='help'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
