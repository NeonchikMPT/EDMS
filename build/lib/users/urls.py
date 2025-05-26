from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('list/', views.user_list, name='user_list'),
    path('documents/<int:user_id>/', views.user_documents, name='user_documents'),
    path('edit/<int:user_id>/', views.user_edit, name='user_edit'),
    path('delete/<int:user_id>/', views.user_delete, name='user_delete'),
    path('export-import/', views.export_import, name='export_import'),
    path('', views.user_list, name='dashboard'),
    path('password/reset/', views.password_reset_request, name='password_reset_request'),
    path('password/reset/<uuid:token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('toggle_email_notifications/<int:user_id>/', views.toggle_email_notifications, name='toggle_email_notifications'),
]
