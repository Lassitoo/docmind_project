# FICHIER: documents/views.py
# VUES DE L'APP DOCUMENTS
# ============================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, JsonResponse
from django.db import models
from .models import Document, DocumentContent, DocumentAnalysis
from .services import DocumentProcessorService
from core.models import ActivityLog
import os


@login_required
def document_list(request):
    """Liste des documents de l'utilisateur"""
    documents = Document.objects.filter(user=request.user).order_by('-uploaded_at')

    # Filtres
    status = request.GET.get('status')
    if status:
        documents = documents.filter(status=status)

    context = {
        'documents': documents,
        'status_filter': status,
    }

    return render(request, 'documents/list.html', context)


@login_required
def document_detail(request, pk):
    """Détails d'un document"""
    document = get_object_or_404(Document, pk=pk, user=request.user)

    # Récupérer le contenu et l'analyse si disponibles
    try:
        content = document.content
    except DocumentContent.DoesNotExist:
        content = None

    try:
        analysis = document.analysis
    except DocumentAnalysis.DoesNotExist:
        analysis = None

    context = {
        'document': document,
        'content': content,
        'analysis': analysis,
    }

    return render(request, 'documents/detail.html', context)


@login_required
def document_upload(request):
    """Upload d'un nouveau document"""
    if request.method == 'POST':
        title = request.POST.get('title')
        file = request.FILES.get('file')
        description = request.POST.get('description', '')

        if not title or not file:
            messages.error(request, 'Veuillez fournir un titre et un fichier.')
            return redirect('documents:upload')

        # Vérifier les quotas
        profile = request.user.profile
        current_docs = Document.objects.filter(user=request.user).count()

        if current_docs >= profile.max_documents:
            messages.error(request, f'Limite de documents atteinte ({profile.max_documents} documents max).')
            return redirect('documents:list')

        # Vérifier l'espace de stockage
        file_size_mb = file.size / (1024 * 1024)
        current_storage = profile.get_used_storage_mb()

        if (current_storage + file_size_mb) > profile.max_storage_mb:
            messages.error(request, 'Espace de stockage insuffisant.')
            return redirect('documents:list')

        # Créer le document
        document = Document.objects.create(
            user=request.user,
            title=title,
            file=file,
            description=description
        )

        # Mettre à jour les statistiques
        profile.total_documents_uploaded += 1
        profile.save()

        # Log de l'activité
        ActivityLog.objects.create(
            user=request.user,
            action_type='upload',
            description=f'Upload du document: {title}',
            metadata={'document_id': document.id}
        )

        messages.success(request, 'Document uploadé avec succès !')

        # Rediriger vers l'analyse
        return redirect('documents:analyze', pk=document.pk)

    return render(request, 'documents/upload.html')


@login_required
def analyze_document(request, pk):
    """Lancer l'analyse d'un document"""
    document = get_object_or_404(Document, pk=pk, user=request.user)

    if document.status == 'completed':
        messages.info(request, 'Ce document a déjà été analysé.')
        return redirect('documents:detail', pk=pk)

    if request.method == 'POST':
        # Lancer l'analyse en arrière-plan (dans une vraie app, utiliser Celery)
        try:
            success = DocumentProcessorService.process_document(document)
            if success:
                messages.success(request, 'Document analysé avec succès !')
            else:
                messages.error(request, 'Erreur lors de l\'analyse du document.')
        except Exception as e:
            messages.error(request, f'Erreur lors de l\'analyse du document: {str(e)}')

        return redirect('documents:detail', pk=pk)

    return render(request, 'documents/analyze.html', {'document': document})


@login_required
def document_content(request, pk):
    """Afficher le contenu extrait d'un document"""
    document = get_object_or_404(Document, pk=pk, user=request.user)

    try:
        content = document.content
    except DocumentContent.DoesNotExist:
        messages.error(request, 'Le document n\'a pas encore été analysé.')
        return redirect('documents:detail', pk=pk)

    context = {
        'document': document,
        'content': content,
    }

    return render(request, 'documents/content.html', context)


@login_required
def document_analysis_view(request, pk):
    """Afficher l'analyse d'un document"""
    document = get_object_or_404(Document, pk=pk, user=request.user)

    try:
        analysis = document.analysis
    except DocumentAnalysis.DoesNotExist:
        messages.error(request, 'Le document n\'a pas encore été analysé.')
        return redirect('documents:detail', pk=pk)

    context = {
        'document': document,
        'analysis': analysis,
    }

    return render(request, 'documents/analysis.html', context)


@login_required
def document_download(request, pk):
    """Télécharger un document"""
    document = get_object_or_404(Document, pk=pk, user=request.user)

    file_path = document.file.path
    if os.path.exists(file_path):
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{document.title}{document.get_file_extension()}"'
        return response
    else:
        messages.error(request, 'Fichier introuvable.')
        return redirect('documents:detail', pk=pk)


@login_required
def document_delete(request, pk):
    """Supprimer un document"""
    document = get_object_or_404(Document, pk=pk, user=request.user)

    if request.method == 'POST':
        title = document.title

        # Supprimer le fichier physique
        if document.file:
            if os.path.exists(document.file.path):
                os.remove(document.file.path)

        # Supprimer le document
        document.delete()

        # Log de l'activité
        ActivityLog.objects.create(
            user=request.user,
            action_type='delete',
            description=f'Suppression du document: {title}'
        )

        messages.success(request, 'Document supprimé avec succès.')
        return redirect('documents:list')

    return render(request, 'documents/delete_confirm.html', {'document': document})


@login_required
def document_search(request):
    """Rechercher dans les documents"""
    query = request.GET.get('q', '')
    results = []

    if query:
        # Recherche simple dans les titres et descriptions
        results = Document.objects.filter(
            user=request.user,
            status='completed'
        ).filter(
            models.Q(title__icontains=query) |
            models.Q(description__icontains=query)
        )

    context = {
        'query': query,
        'results': results,
    }

    return render(request, 'documents/search.html', context)