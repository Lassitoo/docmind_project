# FICHIER: chat/admin.py
# CONFIGURATION ADMIN POUR L'APP CHAT
# ============================================

from django.contrib import admin
from .models import Conversation, Message, QueryContext, Feedback


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['created_at', 'role', 'content', 'tokens_used', 'response_time']
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'use_documents', 'use_external_db', 'created_at', 'updated_at']
    list_filter = ['use_documents', 'use_external_db', 'created_at']
    search_fields = ['title', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['documents']
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'content_preview', 'tokens_used', 'response_time', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['conversation__title', 'content']
    readonly_fields = ['created_at']

    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content

    content_preview.short_description = 'Aperçu du contenu'


@admin.register(QueryContext)
class QueryContextAdmin(admin.ModelAdmin):
    list_display = ['message', 'document', 'relevance_score', 'page_number', 'created_at']
    list_filter = ['document', 'created_at']
    search_fields = ['content']
    readonly_fields = ['created_at']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['message', 'user', 'rating', 'is_helpful', 'is_accurate', 'created_at']
    list_filter = ['rating', 'is_helpful', 'is_accurate', 'created_at']
    search_fields = ['comment']
    readonly_fields = ['created_at']