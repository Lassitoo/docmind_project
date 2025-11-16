# FICHIER: core/models.py
# PARTIE 4: MODÈLES POUR LES PROFILS UTILISATEURS
# ============================================

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """
    Profil étendu pour les utilisateurs
    """
    ROLE_CHOICES = [
        ('client', 'Client'),
        ('admin', 'Administrateur'),
        ('analyst', 'Analyste'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')

    # Informations complémentaires
    company = models.CharField(max_length=255, blank=True, verbose_name="Entreprise")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    address = models.TextField(blank=True, verbose_name="Adresse")

    # Avatar
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # Préférences
    language = models.CharField(max_length=10, default='fr', verbose_name="Langue")
    timezone = models.CharField(max_length=50, default='Europe/Paris')

    # Quotas et limites
    max_documents = models.IntegerField(default=50, verbose_name="Limite de documents")
    max_storage_mb = models.IntegerField(default=1000, verbose_name="Stockage max (MB)")

    # Statistiques
    total_documents_uploaded = models.IntegerField(default=0)
    total_questions_asked = models.IntegerField(default=0)

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        return f"Profil de {self.user.username}"

    def get_used_storage_mb(self):
        """Calcule l'espace de stockage utilisé"""
        from documents.models import Document
        total_size = Document.objects.filter(user=self.user).aggregate(
            models.Sum('file_size')
        )['file_size__sum'] or 0
        return total_size / (1024 * 1024)  # Convertir en MB


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Créer automatiquement un profil lors de la création d'un utilisateur"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Sauvegarder le profil lors de la sauvegarde de l'utilisateur"""
    if hasattr(instance, 'profile'):
        instance.profile.save()


class ActivityLog(models.Model):
    """
    Journal des activités des utilisateurs
    """
    ACTION_TYPES = [
        ('login', 'Connexion'),
        ('logout', 'Déconnexion'),
        ('upload', 'Upload de document'),
        ('delete', 'Suppression'),
        ('query', 'Question posée'),
        ('export', 'Export de données'),
        ('schema_create', 'Création de schéma'),
        ('schema_validate', 'Validation de schéma'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    description = models.TextField(blank=True)

    # Métadonnées
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    # Données supplémentaires en JSON
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Journal d'activité"
        verbose_name_plural = "Journaux d'activités"

    def __str__(self):
        return f"{self.user.username} - {self.action_type} - {self.created_at}"


class SystemSettings(models.Model):
    """
    Paramètres globaux du système (pour les admins)
    """
    key = models.CharField(max_length=255, unique=True, verbose_name="Clé")
    value = models.TextField(verbose_name="Valeur")
    description = models.TextField(blank=True)

    # Type de donnée pour faciliter la conversion
    value_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'Texte'),
            ('integer', 'Entier'),
            ('boolean', 'Booléen'),
            ('json', 'JSON'),
        ],
        default='string'
    )

    is_public = models.BooleanField(default=False, verbose_name="Public")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètre système"
        verbose_name_plural = "Paramètres système"

    def __str__(self):
        return self.key

    def get_value(self):
        """Retourne la valeur avec le bon type"""
        if self.value_type == 'integer':
            return int(self.value)
        elif self.value_type == 'boolean':
            return self.value.lower() in ['true', '1', 'yes']
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        return self.value