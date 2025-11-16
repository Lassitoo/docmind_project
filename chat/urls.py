# FICHIER: chat/urls.py
# URLS DE L'APP CHAT
# ============================================

from django.urls import path
from . import views
from . import editor_views as editor

app_name = 'chat'

urlpatterns = [
    path('', views.conversation_list, name='conversation_list'),
    path('create/', views.conversation_create, name='conversation_create'),
    path('<int:pk>/', views.conversation_detail, name='conversation_detail'),
    path('<int:pk>/send/', views.conversation_send_message, name='send_message'),
    path('<int:pk>/delete/', views.conversation_delete, name='conversation_delete'),
    path('message/<int:message_id>/feedback/', views.message_feedback, name='message_feedback'),

    # Comparaison de documents
    path('compare/', views.documents_compare_select, name='documents_compare_select'),
    path('compare/result/', views.documents_compare_result, name='documents_compare_result'),
    path('compare/api/', views.documents_compare_api, name='documents_compare_api'),

    # Mise à jour de documents
    path('update/generate/', views.documents_update_generate, name='documents_update_generate'),
    path('update/download/', views.documents_update_download, name='documents_update_download'),
    path('update/download-pdf/', views.documents_update_download_pdf, name='documents_update_download_pdf'),
    path('update/apply/', views.documents_apply_changes, name='documents_apply_changes'),

    # Téléchargement du document mis à jour depuis la base de données
    path('download-updated/<int:doc_id>/txt/', views.documents_download_updated, name='documents_download_updated'),
    path('download-updated/<int:doc_id>/pdf/', views.documents_download_updated_pdf, name='documents_download_updated_pdf'),
    path('download-updated/<int:doc_id>/original/', views.documents_download_original_file, name='documents_download_original_file'),

    # Téléchargement PDF du rapport de comparaison
    path('compare/download-pdf/', views.documents_comparison_download_pdf, name='documents_comparison_download_pdf'),

    # Éditeur de documents
    path('editor/<int:document_id>/', editor.document_editor, name='document_editor'),
    path('conversation/<int:conversation_id>/editor/', editor.conversation_editor, name='conversation_editor'),
    path('conversation/<int:conversation_id>/editor/<int:document_id>/', editor.conversation_editor, name='conversation_editor_document'),
    path('editor/<int:document_id>/extract/', editor.extract_document_content, name='extract_document_content'),
    path('editor/<int:document_id>/save/', editor.save_document_changes, name='save_document_changes'),
    path('editor/<int:document_id>/export/', editor.export_document, name='export_document'),
    path('editor/<int:document_id>/autosave/', editor.auto_save_document, name='auto_save_document'),
]