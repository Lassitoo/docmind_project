# FICHIER: documents/urls.py
# URLs DE L'APP DOCUMENTS
# ============================================

from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.document_list, name='list'),
    path('upload/', views.document_upload, name='upload'),
    path('<int:pk>/', views.document_detail, name='detail'),
    path('<int:pk>/content/', views.document_content, name='content'),
    path('<int:pk>/analysis/', views.document_analysis_view, name='analysis'),
    path('<int:pk>/analyze/', views.analyze_document, name='analyze'),
    path('<int:pk>/download/', views.document_download, name='download'),
    path('<int:pk>/delete/', views.document_delete, name='delete'),
    path('search/', views.document_search, name='search'),
]
