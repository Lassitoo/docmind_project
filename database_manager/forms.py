# FICHIER: database_manager/forms.py
# FORMULAIRES POUR LA GESTION DES BASES DE DONNÉES
# ============================================

from django import forms
from .models import ExternalDatabase, DatabaseSchema, DatabaseTable, DatabaseField


class ExternalDatabaseForm(forms.ModelForm):
    """
    Formulaire pour connecter une base de données externe
    """
    class Meta:
        model = ExternalDatabase
        fields = ['name', 'db_type', 'host', 'port', 'database_name', 'username', 'password', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la connexion'
            }),
            'db_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'host': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'localhost ou adresse IP'
            }),
            'port': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '5432'
            }),
            'database_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la base de données'
            }),
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Utilisateur'
            }),
            'password': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Mot de passe'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description (optionnel)'
            })
        }

    def clean_port(self):
        port = self.cleaned_data.get('port')
        if port and (port < 1 or port > 65535):
            raise forms.ValidationError("Le port doit être entre 1 et 65535")
        return port


class DatabaseSchemaForm(forms.ModelForm):
    """
    Formulaire pour créer/modifier un schéma de base de données
    """
    class Meta:
        model = DatabaseSchema
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du schéma'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description du schéma'
            })
        }


class DatabaseTableForm(forms.ModelForm):
    """
    Formulaire pour ajouter/modifier une table
    """
    class Meta:
        model = DatabaseTable
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la table (snake_case)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Description de la table'
            })
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Valider que le nom est en snake_case
            import re
            if not re.match(r'^[a-z][a-z0-9_]*$', name):
                raise forms.ValidationError(
                    "Le nom doit être en snake_case (minuscules, chiffres et underscores uniquement)"
                )
        return name


class DatabaseFieldForm(forms.ModelForm):
    """
    Formulaire pour ajouter/modifier un champ
    """
    class Meta:
        model = DatabaseField
        fields = [
            'name', 'field_type', 'is_primary_key', 'is_nullable',
            'is_unique', 'default_value', 'max_length', 'description'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du champ'
            }),
            'field_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_primary_key': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_nullable': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_unique': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'default_value': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Valeur par défaut (optionnel)'
            }),
            'max_length': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '255'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Description du champ'
            })
        }


class SchemaValidationForm(forms.Form):
    """
    Formulaire pour valider un schéma
    """
    confirm = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label="Je confirme vouloir valider ce schéma"
    )
    comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Commentaires (optionnel)'
        }),
        label="Commentaires"
    )
