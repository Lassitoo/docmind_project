# FICHIER: documents/admin.py
# CONFIGURATION ADMIN POUR L'APP DOCUMENTS
# ============================================

from django.contrib import admin
from .models import Document, DocumentContent, DocumentAnalysis, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'file_type', 'status', 'uploaded_at']
    list_filter = ['status', 'file_type', 'uploaded_at']
    search_fields = ['title', 'user__username', 'description']
    readonly_fields = ['uploaded_at', 'analyzed_at', 'file_size']
    date_hierarchy = 'uploaded_at'

    fieldsets = (
        ('Informations principales', {
            'fields': ('user', 'title', 'file', 'description')
        }),
        ('Statut', {
            'fields': ('status', 'file_type', 'file_size')
        }),
        ('Dates', {
            'fields': ('uploaded_at', 'analyzed_at')
        }),
    )


@admin.register(DocumentContent)
class DocumentContentAdmin(admin.ModelAdmin):
    list_display = ['document', 'word_count', 'page_count', 'language', 'created_at']
    list_filter = ['language', 'created_at']
    search_fields = ['document__title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DocumentAnalysis)
class DocumentAnalysisAdmin(admin.ModelAdmin):
    list_display = ['document', 'created_at']
    search_fields = ['document__title', 'summary']
    readonly_fields = ['created_at']


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['document', 'chunk_index', 'page_number', 'created_at']
    list_filter = ['document', 'created_at']
    search_fields = ['document__title', 'content']
    readonly_fields = ['created_at']