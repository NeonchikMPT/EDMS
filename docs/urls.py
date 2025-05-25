from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_documents, name='my_documents'),
    path('create/', views.document_create, name='document_create'),
    path('received/', views.received_documents, name='received_documents'),
    path('sign/<int:doc_id>/', views.document_sign, name='document_sign'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('logs/<int:doc_id>/', views.document_logs, name='document_logs'),
    path('notifications/read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/check/', views.check_notifications, name='check_notifications'),
    path('view/<int:doc_id>/', views.document_view, name='document_view'),
    path('comment/<int:doc_id>/', views.add_comment, name='add_comment'),
    path('search-users/', views.search_users, name='search_users'),
    path('edit/<int:doc_id>/', views.document_edit, name='document_edit'),
    path('delete/<int:doc_id>/', views.document_delete, name='document_delete'),
]
