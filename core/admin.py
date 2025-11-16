# FICHIER: core/admin.py
# CONFIGURATION ADMIN POUR L'APP CORE
# ============================================

from django.contrib import admin
from .models import UserProfile, ActivityLog, SystemSettings


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'company', 'total_documents_uploaded', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['user__username', 'user__email', 'company']
    readonly_fields = ['created_at', 'updated_at', 'total_documents_uploaded', 'total_questions_asked']


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action_type', 'created_at', 'ip_address']
    list_filter = ['action_type', 'created_at']
    search_fields = ['user__username', 'description']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_type', 'is_public', 'updated_at']
    list_filter = ['value_type', 'is_public']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']