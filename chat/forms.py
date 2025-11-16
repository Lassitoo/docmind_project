# FICHIER: chat/forms.py
# FORMULAIRES POUR LE CHAT
# ============================================

from django import forms
from .models import Conversation, Feedback
from documents.models import Document
from database_manager.models import ExternalDatabase


class ConversationCreateForm(forms.ModelForm):
    """
    Formulaire pour créer une nouvelle conversation
    """
    documents = forms.ModelMultipleChoiceField(
        queryset=Document.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Documents à utiliser"
    )

    class Meta:
        model = Conversation
        fields = ['title', 'use_documents', 'use_external_db', 'external_db']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre de la conversation'
            }),
            'use_documents': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'use_external_db': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'external_db': forms.Select(attrs={
                'class': 'form-select'
            })
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            # Filtrer les documents par utilisateur
            self.fields['documents'].queryset = Document.objects.filter(
                user=user,
                status='completed'
            )
            # Filtrer les bases externes par utilisateur
            self.fields['external_db'].queryset = ExternalDatabase.objects.filter(
                user=user,
                status='connected'
            )


class MessageForm(forms.Form):
    """
    Formulaire pour envoyer un message
    """
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Posez votre question...'
        }),
        label="Votre question"
    )


class FeedbackForm(forms.ModelForm):
    """
    Formulaire pour donner un feedback sur une réponse
    """
    class Meta:
        model = Feedback
        fields = ['rating', 'is_helpful', 'is_accurate', 'comment']
        widgets = {
            'rating': forms.RadioSelect(attrs={
                'class': 'form-check-input'
            }),
            'is_helpful': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_accurate': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Commentaire (optionnel)'
            })
        }
