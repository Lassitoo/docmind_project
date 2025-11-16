# FICHIER: chat/models.py
# PARTIE 2: MODÈLES POUR LE CHAT ET LES CONVERSATIONS
# ============================================

from django.db import models
from django.contrib.auth.models import User
from documents.models import Document
import json
from database_manager.models import ExternalDatabase


class Conversation(models.Model):
    """
    Représente une session de conversation entre l'utilisateur et l'IA
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=255, verbose_name="Titre de la conversation")

    # Sources de données utilisées pour cette conversation
    documents = models.ManyToManyField(Document, blank=True, related_name='conversations')
    external_db = models.ForeignKey(
        'database_manager.ExternalDatabase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )

    # Configuration de la conversation
    use_documents = models.BooleanField(default=True, verbose_name="Utiliser les documents")
    use_external_db = models.BooleanField(default=False, verbose_name="Utiliser la base externe")

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def get_message_count(self):
        return self.messages.count()


class Message(models.Model):
    """
    Messages individuels dans une conversation
    """
    ROLE_CHOICES = [
        ('user', 'Utilisateur'),
        ('assistant', 'Assistant'),
        ('system', 'Système'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField(verbose_name="Contenu")

    # Métriques
    tokens_used = models.IntegerField(default=0, verbose_name="Tokens utilisés")
    response_time = models.FloatField(default=0.0, verbose_name="Temps de réponse (s)")

    # Sources utilisées pour générer la réponse
    sources_used = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self):
        return f"{self.conversation.title} - {self.role} - {self.created_at}"


class QueryContext(models.Model):
    """
    Contexte récupéré pour répondre à une question
    """
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='contexts')

    # Source du contexte
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='query_contexts'
    )

    # Contenu du contexte
    content = models.TextField(verbose_name="Contenu du contexte")

    # Métadonnées
    relevance_score = models.FloatField(verbose_name="Score de pertinence")
    page_number = models.IntegerField(null=True, blank=True)
    chunk_index = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-relevance_score']
        verbose_name = "Contexte de requête"
        verbose_name_plural = "Contextes de requêtes"

    def __str__(self):
        return f"Contexte pour {self.message.id} - Score: {self.relevance_score}"


class Feedback(models.Model):
    """
    Feedback des utilisateurs sur les réponses
    """
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='feedbacks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')

    # Types de feedback
    rating = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        verbose_name="Note (1-5)"
    )
    is_helpful = models.BooleanField(null=True, blank=True, verbose_name="Utile?")
    is_accurate = models.BooleanField(null=True, blank=True, verbose_name="Précis?")

    # Commentaire
    comment = models.TextField(blank=True, verbose_name="Commentaire")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Feedback"
        verbose_name_plural = "Feedbacks"

    def __str__(self):
        return f"Feedback pour message {self.message.id} - Note: {self.rating}"


class ConversationDocument(models.Model):
    """
    Relation entre conversations et documents avec métadonnées
    Pour le système d'agent intelligent
    """
    ROLE_CHOICES = [
        ('context', 'Contexte'),  # Document de référence
        ('source', 'Source'),     # Document source pour comparaison
        ('target', 'Cible'),      # Document cible pour modification
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='conversation_documents'
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='document_conversations'
    )

    # Métadonnées
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='context',
        verbose_name="Rôle du document"
    )
    added_at = models.DateTimeField(auto_now_add=True)
    added_by_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ajouté par le message"
    )

    class Meta:
        verbose_name = "Document de conversation"
        verbose_name_plural = "Documents de conversation"
        ordering = ['added_at']
        unique_together = ['conversation', 'document']

    def __str__(self):
        return f"{self.document.title} - {self.conversation.title} ({self.role})"


class GeneratedFile(models.Model):
    """
    Fichiers générés par l'agent intelligent
    """
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('docx', 'Word Document'),
        ('txt', 'Text'),
        ('json', 'JSON'),
        ('csv', 'CSV'),
    ]

    TOOL_CHOICES = [
        ('compare', 'Comparaison de documents'),
        ('merge', 'Fusion de documents'),
        ('generate', 'Génération personnalisée'),
        ('extract', 'Extraction d\'informations'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='generated_files'
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_files',
        verbose_name="Message associé"
    )

    # Fichier
    file = models.FileField(
        upload_to='generated/%Y/%m/%d/',
        verbose_name="Fichier généré"
    )
    file_type = models.CharField(
        max_length=10,
        choices=FILE_TYPE_CHOICES,
        verbose_name="Type de fichier"
    )
    file_size = models.IntegerField(
        default=0,
        verbose_name="Taille (bytes)"
    )

    # Métadonnées
    title = models.CharField(
        max_length=255,
        verbose_name="Titre du fichier"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    tool_used = models.CharField(
        max_length=20,
        choices=TOOL_CHOICES,
        verbose_name="Outil utilisé"
    )

    # Documents sources utilisés pour générer ce fichier
    source_documents = models.ManyToManyField(
        Document,
        blank=True,
        related_name='generated_from'
    )

    # Paramètres utilisés pour la génération
    generation_params = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Paramètres de génération"
    )

    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    downloaded_count = models.IntegerField(
        default=0,
        verbose_name="Nombre de téléchargements"
    )

    class Meta:
        verbose_name = "Fichier généré"
        verbose_name_plural = "Fichiers générés"
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.title} ({self.file_type}) - {self.generated_at.strftime('%Y-%m-%d')}"

    def increment_download(self):
        """Incrémente le compteur de téléchargements"""
        self.downloaded_count += 1
        self.save(update_fields=['downloaded_count'])
