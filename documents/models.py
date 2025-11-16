# FICHIER: documents/models.py
# PARTIE 1: MODÈLES POUR LA GESTION DES DOCUMENTS
# ============================================

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os


class Document(models.Model):
    """
    Modèle pour stocker les documents uploadés par les clients
    """
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours d\'analyse'),
        ('completed', 'Analysé'),
        ('error', 'Erreur'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255, verbose_name="Titre du document")
    file = models.FileField(upload_to='documents/%Y/%m/%d/', verbose_name="Fichier")
    file_type = models.CharField(max_length=50, blank=True)
    file_size = models.IntegerField(default=0, verbose_name="Taille (bytes)")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    uploaded_at = models.DateTimeField(auto_now_add=True)
    analyzed_at = models.DateTimeField(null=True, blank=True)

    description = models.TextField(blank=True, verbose_name="Description")

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Document"
        verbose_name_plural = "Documents"

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def get_file_extension(self):
        """Retourne l'extension du fichier"""
        return os.path.splitext(self.file.name)[1].lower()

    def save(self, *args, **kwargs):
        """Override save pour extraire automatiquement le type et la taille"""
        if self.file:
            self.file_type = self.get_file_extension()
            self.file_size = self.file.size
        super().save(*args, **kwargs)


class DocumentContent(models.Model):
    """
    Contenu extrait du document après analyse
    """
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='content')
    raw_text = models.TextField(verbose_name="Texte brut extrait")
    processed_text = models.TextField(blank=True, verbose_name="Texte traité")

    # Métadonnées extraites
    word_count = models.IntegerField(default=0)
    page_count = models.IntegerField(default=0)
    language = models.CharField(max_length=10, blank=True)

    # Stockage des embeddings pour la recherche sémantique
    embeddings = models.JSONField(null=True, blank=True)

    # Stockage de la structure du document (tableaux, mise en page) pour PDF
    pdf_structure = models.JSONField(null=True, blank=True, verbose_name="Structure PDF extraite")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contenu du document"
        verbose_name_plural = "Contenus des documents"

    def __str__(self):
        return f"Contenu de {self.document.title}"


class DocumentAnalysis(models.Model):
    """
    Résultats de l'analyse IA du document
    """
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='analysis')

    # Résumé généré par l'IA
    summary = models.TextField(verbose_name="Résumé")

    # Entités extraites (noms, dates, lieux, etc.)
    entities = models.JSONField(default=dict, blank=True)

    # Mots-clés identifiés
    keywords = models.JSONField(default=list, blank=True)

    # Structure identifiée (sections, chapitres, etc.)
    structure = models.JSONField(default=dict, blank=True)

    # Type de document détecté
    detected_document_type = models.CharField(max_length=100, blank=True, verbose_name="Type de document")

    # Langue détectée
    language = models.CharField(max_length=50, blank=True, verbose_name="Langue")

    # Score de confiance de l'analyse (0-100)
    confidence_score = models.FloatField(null=True, blank=True, verbose_name="Score de confiance")

    # Métadonnées supplémentaires
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Analyse du document"
        verbose_name_plural = "Analyses des documents"

    def __str__(self):
        return f"Analyse de {self.document.title}"


class DocumentChunk(models.Model):
    """
    Segments du document pour améliorer la recherche et les réponses
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')

    chunk_index = models.IntegerField(verbose_name="Index du segment")
    content = models.TextField(verbose_name="Contenu du segment")

    # Position dans le document
    page_number = models.IntegerField(null=True, blank=True)
    start_char = models.IntegerField(null=True, blank=True)
    end_char = models.IntegerField(null=True, blank=True)

    # Embedding pour ce segment
    embedding = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'chunk_index']
        verbose_name = "Segment de document"
        verbose_name_plural = "Segments de documents"

    def __str__(self):
        return f"{self.document.title} - Segment {self.chunk_index}"