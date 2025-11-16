# FICHIER: documents/forms.py
# FORMULAIRES POUR LA GESTION DES DOCUMENTS
# ============================================

from django import forms
from .models import Document


class DocumentUploadForm(forms.ModelForm):
    """
    Formulaire pour l'upload de documents
    """
    class Meta:
        model = Document
        fields = ['title', 'file', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre du document'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.docx,.doc,.txt'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description du document (optionnel)'
            })
        }
        labels = {
            'title': 'Titre',
            'file': 'Fichier',
            'description': 'Description'
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Vérifier la taille (max 50 MB)
            if file.size > 50 * 1024 * 1024:
                raise forms.ValidationError("Le fichier est trop volumineux (max 50 MB)")

            # Vérifier l'extension
            allowed_extensions = ['.pdf', '.docx', '.doc', '.txt']
            ext = file.name.split('.')[-1].lower()
            if f'.{ext}' not in allowed_extensions:
                raise forms.ValidationError(
                    f"Type de fichier non supporté. Formats acceptés: {', '.join(allowed_extensions)}"
                )

        return file


class DocumentSearchForm(forms.Form):
    """
    Formulaire de recherche de documents
    """
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher un document...'
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Tous les statuts')] + Document.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
