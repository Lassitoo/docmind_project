# FICHIER: database_manager/admin.py
# CONFIGURATION ADMIN POUR L'APP DATABASE_MANAGER
# ============================================

from django.contrib import admin
from .models import (
    DatabaseSchema, DatabaseTable, DatabaseField, DatabaseRelation,
    ExternalDatabase, QueryHistory, DataExtraction
)


class DatabaseFieldInline(admin.TabularInline):
    model = DatabaseField
    extra = 1


@admin.register(DatabaseSchema)
class DatabaseSchemaAdmin(admin.ModelAdmin):
    list_display = ['name', 'document', 'status', 'validated_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'description', 'document__title']
    readonly_fields = ['created_at', 'updated_at', 'validated_at']
    date_hierarchy = 'created_at'


@admin.register(DatabaseTable)
class DatabaseTableAdmin(admin.ModelAdmin):
    list_display = ['name', 'schema', 'created_at']
    list_filter = ['schema', 'created_at']
    search_fields = ['name', 'description']
    inlines = [DatabaseFieldInline]


@admin.register(DatabaseField)
class DatabaseFieldAdmin(admin.ModelAdmin):
    list_display = ['name', 'table', 'field_type', 'is_primary_key', 'is_nullable', 'is_unique']
    list_filter = ['field_type', 'is_primary_key', 'is_nullable', 'is_unique']
    search_fields = ['name', 'description']


@admin.register(DatabaseRelation)
class DatabaseRelationAdmin(admin.ModelAdmin):
    list_display = ['from_table', 'to_table', 'relation_type', 'schema']
    list_filter = ['relation_type', 'schema']


@admin.register(ExternalDatabase)
class ExternalDatabaseAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'db_type', 'status', 'host', 'last_connection_test']
    list_filter = ['db_type', 'status', 'created_at']
    search_fields = ['name', 'user__username', 'host']
    readonly_fields = ['created_at', 'updated_at', 'last_connection_test']


@admin.register(QueryHistory)
class QueryHistoryAdmin(admin.ModelAdmin):
    list_display = ['external_db', 'user', 'success', 'execution_time', 'created_at']
    list_filter = ['success', 'created_at']
    search_fields = ['query', 'user__username']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(DataExtraction)
class DataExtractionAdmin(admin.ModelAdmin):
    list_display = ['schema', 'document', 'status', 'confidence_score', 'validated_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['schema__name', 'document__title']
    readonly_fields = ['created_at', 'updated_at', 'validated_at']
    date_hierarchy = 'created_at'