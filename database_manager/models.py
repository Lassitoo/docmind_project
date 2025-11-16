# FICHIER: database_manager/models.py
# PARTIE 3: MODÈLES POUR LA GESTION DES BASES DE DONNÉES
# ============================================

from django.db import models
from django.contrib.auth.models import User
from documents.models import Document


class DatabaseSchema(models.Model):
    """
    Schéma de base de données généré automatiquement à partir d'un document
    """
    STATUS_CHOICES = [
        ('proposed', 'Proposé'),
        ('modified', 'Modifié'),
        ('validated', 'Validé'),
        ('implemented', 'Implémenté'),
        ('rejected', 'Rejeté'),
    ]

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='database_schemas'
    )

    name = models.CharField(max_length=255, verbose_name="Nom du schéma")
    description = models.TextField(blank=True, verbose_name="Description")

    # Schéma JSON contenant les tables, champs, relations
    schema_definition = models.JSONField(verbose_name="Définition du schéma")

    # Statut du schéma
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='proposed')

    # Validation
    validated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validated_schemas'
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Schéma de base de données"
        verbose_name_plural = "Schémas de bases de données"

    def __str__(self):
        return f"{self.name} - {self.status}"


class DatabaseTable(models.Model):
    """
    Table dans un schéma de base de données
    """
    schema = models.ForeignKey(
        DatabaseSchema,
        on_delete=models.CASCADE,
        related_name='tables'
    )

    name = models.CharField(max_length=255, verbose_name="Nom de la table")
    description = models.TextField(blank=True)

    # Position pour l'affichage visuel
    position_x = models.IntegerField(default=0)
    position_y = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Table"
        verbose_name_plural = "Tables"

    def __str__(self):
        return f"{self.schema.name}.{self.name}"


class DatabaseField(models.Model):
    """
    Champ dans une table de base de données
    """
    FIELD_TYPES = [
        ('integer', 'Integer'),
        ('string', 'String'),
        ('text', 'Text'),
        ('boolean', 'Boolean'),
        ('date', 'Date'),
        ('datetime', 'DateTime'),
        ('decimal', 'Decimal'),
        ('foreign_key', 'Foreign Key'),
    ]

    table = models.ForeignKey(
        DatabaseTable,
        on_delete=models.CASCADE,
        related_name='fields'
    )

    name = models.CharField(max_length=255, verbose_name="Nom du champ")
    field_type = models.CharField(max_length=50, choices=FIELD_TYPES)

    # Contraintes
    is_primary_key = models.BooleanField(default=False)
    is_nullable = models.BooleanField(default=True)
    is_unique = models.BooleanField(default=False)

    # Valeur par défaut
    default_value = models.CharField(max_length=255, blank=True)

    # Métadonnées
    max_length = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

    # Ordre d'affichage
    order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Champ"
        verbose_name_plural = "Champs"

    def __str__(self):
        return f"{self.table.name}.{self.name} ({self.field_type})"


class DatabaseRelation(models.Model):
    """
    Relations entre les tables
    """
    RELATION_TYPES = [
        ('one_to_one', 'One to One'),
        ('one_to_many', 'One to Many'),
        ('many_to_many', 'Many to Many'),
    ]

    schema = models.ForeignKey(
        DatabaseSchema,
        on_delete=models.CASCADE,
        related_name='relations'
    )

    from_table = models.ForeignKey(
        DatabaseTable,
        on_delete=models.CASCADE,
        related_name='relations_from'
    )
    to_table = models.ForeignKey(
        DatabaseTable,
        on_delete=models.CASCADE,
        related_name='relations_to'
    )

    from_field = models.ForeignKey(
        DatabaseField,
        on_delete=models.CASCADE,
        related_name='relations_from',
        null=True,
        blank=True
    )
    to_field = models.ForeignKey(
        DatabaseField,
        on_delete=models.CASCADE,
        related_name='relations_to',
        null=True,
        blank=True
    )

    relation_type = models.CharField(max_length=20, choices=RELATION_TYPES)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Relation"
        verbose_name_plural = "Relations"

    def __str__(self):
        return f"{self.from_table.name} -> {self.to_table.name} ({self.relation_type})"


class ExternalDatabase(models.Model):
    """
    Base de données externe connectée par un client
    """
    DB_TYPES = [
        ('postgresql', 'PostgreSQL'),
        ('mysql', 'MySQL'),
        ('sqlite', 'SQLite'),
        ('mssql', 'Microsoft SQL Server'),
        ('oracle', 'Oracle'),
    ]

    STATUS_CHOICES = [
        ('connected', 'Connecté'),
        ('disconnected', 'Déconnecté'),
        ('error', 'Erreur'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='external_databases')

    name = models.CharField(max_length=255, verbose_name="Nom de la connexion")
    db_type = models.CharField(max_length=50, choices=DB_TYPES)

    # Informations de connexion (à chiffrer en production!)
    host = models.CharField(max_length=255)
    port = models.IntegerField()
    database_name = models.CharField(max_length=255)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)  # À chiffrer!

    # Statut
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disconnected')
    last_connection_test = models.DateTimeField(null=True, blank=True)

    # Métadonnées
    description = models.TextField(blank=True)

    # Schéma importé
    imported_schema = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Base de données externe"
        verbose_name_plural = "Bases de données externes"

    def __str__(self):
        return f"{self.name} ({self.db_type}) - {self.user.username}"


class QueryHistory(models.Model):
    """
    Historique des requêtes SQL exécutées sur les bases externes
    """
    external_db = models.ForeignKey(
        ExternalDatabase,
        on_delete=models.CASCADE,
        related_name='query_history'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='db_queries')

    query = models.TextField(verbose_name="Requête SQL")

    # Résultats
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    execution_time = models.FloatField(default=0.0, verbose_name="Temps d'exécution (s)")
    rows_affected = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Historique de requête"
        verbose_name_plural = "Historiques de requêtes"

    def __str__(self):
        return f"Query on {self.external_db.name} - {self.created_at}"


class DataExtraction(models.Model):
    """
    Extraction de données d'un document pour remplir un schéma de base de données
    """
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('extracted', 'Extrait'),
        ('validated', 'Validé'),
        ('rejected', 'Rejeté'),
        ('imported', 'Importé'),
    ]

    schema = models.ForeignKey(
        DatabaseSchema,
        on_delete=models.CASCADE,
        related_name='data_extractions',
        verbose_name="Schéma cible"
    )

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='data_extractions',
        verbose_name="Document source"
    )

    # JSON contenant les données extraites structurées selon le schéma
    extracted_data = models.JSONField(
        verbose_name="Données extraites",
        help_text="JSON contenant les données du document formatées selon le schéma"
    )

    # Statut de l'extraction
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Validation
    validated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validated_extractions'
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    # Métadonnées sur l'extraction
    confidence_score = models.FloatField(
        default=0.0,
        verbose_name="Score de confiance",
        help_text="Score de confiance de l'extraction (0-1)"
    )

    extraction_notes = models.TextField(
        blank=True,
        verbose_name="Notes d'extraction",
        help_text="Notes générées par l'IA sur l'extraction"
    )

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Extraction de données"
        verbose_name_plural = "Extractions de données"

    def __str__(self):
        return f"Extraction: {self.document.title} → {self.schema.name}"
