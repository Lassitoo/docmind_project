# FICHIER: database_manager/urls.py
# URLs DE L'APP DATABASE_MANAGER
# ============================================

from django.urls import path
from . import views

app_name = 'database_manager'

urlpatterns = [
    # Bases de données externes
    path('external/', views.external_database_list, name='external_database_list'),
    path('external/create/', views.external_database_create, name='external_database_create'),
    path('external/<int:pk>/', views.external_database_detail, name='external_database_detail'),
    path('external/<int:pk>/test/', views.external_database_test, name='external_database_test'),

    # Schémas
    path('schemas/', views.schema_list, name='schema_list'),
    path('schemas/generate/<int:document_id>/', views.schema_generate, name='schema_generate'),
    path('schemas/<int:pk>/', views.schema_detail, name='schema_detail'),
    path('schemas/<int:pk>/edit/', views.schema_edit, name='schema_edit'),
    path('schemas/<int:pk>/validate/', views.schema_validate, name='schema_validate'),
    path('schemas/<int:pk>/download-sql/', views.schema_download_sql, name='schema_download_sql'),

    # Tables et champs
    path('schemas/<int:schema_id>/table/add/', views.table_add, name='table_add'),
    path('tables/<int:table_id>/field/add/', views.field_add, name='field_add'),

    # Extractions de données
    path('extractions/', views.data_extraction_list, name='data_extraction_list'),
    path('extractions/<int:pk>/', views.data_extraction_detail, name='data_extraction_detail'),
    path('extractions/<int:pk>/validate/', views.data_extraction_validate, name='data_extraction_validate'),
    path('extractions/<int:pk>/reject/', views.data_extraction_reject, name='data_extraction_reject'),
    path('extractions/<int:pk>/download-sql/', views.data_extraction_download_sql, name='data_extraction_download_sql'),
    path('extractions/<int:pk>/download-json/', views.data_extraction_download_json, name='data_extraction_download_json'),
    path('schemas/<int:schema_id>/extract/<int:document_id>/', views.data_extraction_create, name='data_extraction_create'),
]
