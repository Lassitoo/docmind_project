# FICHIER: chat/views.py
# VUES POUR LE CHAT ET LES CONVERSATIONS
# ============================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from .models import Conversation, Message, Feedback, GeneratedFile
from .forms import ConversationCreateForm, MessageForm, FeedbackForm
from .services import ChatService, DocumentComparisonService, DocumentUpdateService
from .agent_service import AgentService
from documents.models import Document
import json


@login_required
def conversation_list(request):
    """Liste des conversations de l'utilisateur"""
    conversations = Conversation.objects.filter(user=request.user).order_by('-updated_at')

    context = {
        'conversations': conversations,
    }

    return render(request, 'chat/conversation_list.html', context)


@login_required
def conversation_create(request):
    """Créer une nouvelle conversation"""
    if request.method == 'POST':
        form = ConversationCreateForm(request.POST, user=request.user)
        if form.is_valid():
            conversation = form.save(commit=False)
            conversation.user = request.user

            # Associer les documents sélectionnés
            documents = form.cleaned_data.get('documents')

            # Activer use_documents si des documents sont sélectionnés
            if documents:
                conversation.use_documents = True

            conversation.save()

            if documents:
                conversation.documents.set(documents)

            messages.success(request, 'Conversation créée avec succès!')
            return redirect('chat:conversation_detail', pk=conversation.pk)
    else:
        form = ConversationCreateForm(user=request.user)

    context = {
        'form': form,
    }

    return render(request, 'chat/conversation_create.html', context)


@login_required
def conversation_detail(request, pk):
    """Page de conversation avec chat"""
    conversation = get_object_or_404(Conversation, pk=pk, user=request.user)

    # Récupérer l'historique des messages
    messages_list = conversation.messages.all().order_by('created_at')

    # Formulaire pour envoyer un message
    form = MessageForm()

    # Récupérer tous les documents de la conversation
    all_documents = list(conversation.documents.all())
    primary_document = all_documents[0] if all_documents else None

    context = {
        'conversation': conversation,
        'messages_list': messages_list,
        'form': form,
        'primary_document': primary_document,
        'all_documents': all_documents,
        'documents_count': len(all_documents),
    }

    return render(request, 'chat/conversation_detail.html', context)


@login_required
@require_POST
def conversation_send_message(request, pk):
    """Envoyer un message dans une conversation (API)"""
    conversation = get_object_or_404(Conversation, pk=pk, user=request.user)

    form = MessageForm(request.POST)
    if form.is_valid():
        query = form.cleaned_data['content']

        try:
            # Utiliser l'Agent intelligent par défaut (nouvelle approche)
            use_agent = request.POST.get('use_agent', 'true').lower() == 'true'

            if use_agent:
                # Agent intelligent avec tools
                result = AgentService.process_message(
                    conversation_id=conversation.id,
                    user_message=query
                )

                if result.get('success'):
                    # Récupérer les fichiers générés
                    generated_files = result.get('generated_files', [])
                    files_data = []

                    for gen_file in generated_files:
                        files_data.append({
                            'id': gen_file.id,
                            'title': gen_file.title,
                            'file_type': gen_file.file_type,
                            'url': gen_file.file.url if gen_file.file else None
                        })

                    return JsonResponse({
                        'success': True,
                        'user_message': {
                            'content': query
                        },
                        'assistant_message': {
                            'content': result.get('content', ''),
                            'response_time': result.get('response_time', 0),
                            'tools_used': result.get('tools_used', []),
                            'generated_files': files_data
                        }
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': result.get('error', 'Erreur inconnue')
                    }, status=500)

            else:
                # Ancien ChatService (fallback)
                assistant_message = ChatService.process_user_query(conversation, query)

                return JsonResponse({
                    'success': True,
                    'user_message': {
                        'content': query,
                        'created_at': assistant_message.created_at.isoformat()
                    },
                    'assistant_message': {
                        'content': assistant_message.content,
                        'created_at': assistant_message.created_at.isoformat(),
                        'response_time': assistant_message.response_time
                    }
                })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Données invalides'
    }, status=400)


@login_required
def conversation_delete(request, pk):
    """Supprimer une conversation"""
    conversation = get_object_or_404(Conversation, pk=pk, user=request.user)

    if request.method == 'POST':
        conversation.delete()
        messages.success(request, 'Conversation supprimée avec succès!')
        return redirect('chat:conversation_list')

    return render(request, 'chat/conversation_confirm_delete.html', {'conversation': conversation})


@login_required
@require_POST
def message_feedback(request, message_id):
    """Ajouter un feedback sur un message (API)"""
    message = get_object_or_404(Message, pk=message_id, conversation__user=request.user)

    rating = request.POST.get('rating')
    is_helpful = request.POST.get('is_helpful') == 'true'
    is_accurate = request.POST.get('is_accurate') == 'true'
    comment = request.POST.get('comment', '')

    try:
        feedback, created = Feedback.objects.get_or_create(
            message=message,
            user=request.user,
            defaults={
                'rating': rating,
                'is_helpful': is_helpful,
                'is_accurate': is_accurate,
                'comment': comment
            }
        )

        if not created:
            feedback.rating = rating
            feedback.is_helpful = is_helpful
            feedback.is_accurate = is_accurate
            feedback.comment = comment
            feedback.save()

        return JsonResponse({
            'success': True,
            'message': 'Feedback enregistré'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def documents_compare_select(request):
    """Page de sélection des documents à comparer"""
    documents = Document.objects.filter(user=request.user, status='completed').order_by('-uploaded_at')

    context = {
        'documents': documents,
    }

    return render(request, 'chat/documents_compare_select.html', context)


@login_required
def documents_compare_result(request):
    """Affiche les résultats de la comparaison de deux documents"""
    doc1_id = request.GET.get('doc1')
    doc2_id = request.GET.get('doc2')

    if not doc1_id or not doc2_id:
        messages.error(request, 'Veuillez sélectionner deux documents à comparer')
        return redirect('chat:documents_compare_select')

    # Récupérer les documents
    doc1 = get_object_or_404(Document, pk=doc1_id, user=request.user)
    doc2 = get_object_or_404(Document, pk=doc2_id, user=request.user)

    # Comparer les documents
    comparison_result = DocumentComparisonService.compare_documents(doc1, doc2)

    if not comparison_result.get('success'):
        messages.error(request, comparison_result.get('error', 'Erreur lors de la comparaison'))
        return redirect('chat:documents_compare_select')

    # Stocker les données en session pour le téléchargement PDF
    request.session['comparison_data'] = {
        'doc1': {
            'id': doc1.id,
            'title': doc1.title,
            'word_count': comparison_result.get('doc1', {}).get('word_count')
        },
        'doc2': {
            'id': doc2.id,
            'title': doc2.title,
            'word_count': comparison_result.get('doc2', {}).get('word_count')
        },
        'comparison': comparison_result.get('comparison'),
        'processing_time': comparison_result.get('processing_time')
    }

    context = {
        'doc1': doc1,
        'doc2': doc2,
        'comparison': comparison_result,
    }

    return render(request, 'chat/documents_compare_result.html', context)


@login_required
@require_POST
def documents_compare_api(request):
    """API pour comparer deux documents (AJAX)"""
    doc1_id = request.POST.get('doc1_id')
    doc2_id = request.POST.get('doc2_id')

    if not doc1_id or not doc2_id:
        return JsonResponse({
            'success': False,
            'error': 'IDs de documents manquants'
        }, status=400)

    try:
        doc1 = Document.objects.get(pk=doc1_id, user=request.user)
        doc2 = Document.objects.get(pk=doc2_id, user=request.user)

        comparison_result = DocumentComparisonService.compare_documents(doc1, doc2)

        return JsonResponse(comparison_result)

    except Document.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Document non trouvé'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def documents_update_generate(request):
    """Génère un document mis à jour basé sur les différences (API)"""
    doc1_id = request.POST.get('doc1_id')
    doc2_id = request.POST.get('doc2_id')
    selected_changes = request.POST.get('selected_changes')

    if not doc1_id or not doc2_id:
        return JsonResponse({
            'success': False,
            'error': 'IDs de documents manquants'
        }, status=400)

    try:
        doc1 = Document.objects.get(pk=doc1_id, user=request.user)
        doc2 = Document.objects.get(pk=doc2_id, user=request.user)

        # Parser les changements sélectionnés
        changes_list = None
        if selected_changes:
            try:
                changes_list = json.loads(selected_changes)
            except json.JSONDecodeError:
                changes_list = [selected_changes]

        # Générer le document mis à jour
        update_result = DocumentUpdateService.generate_updated_document(doc1, doc2, changes_list)

        if update_result.get('success'):
            # Stocker le résultat en session pour téléchargement
            request.session['updated_document'] = {
                'content': update_result['updated_content']['content'],
                'type': update_result['updated_content']['type'],
                'message': update_result['updated_content'].get('message', ''),
                'original_title': doc1.title,
                'processing_time': update_result['processing_time']
            }

        return JsonResponse(update_result)

    except Document.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Document non trouvé'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def documents_update_download(request):
    """Télécharge le document mis à jour généré (TXT)"""
    from django.http import HttpResponse

    updated_doc = request.session.get('updated_document')

    if not updated_doc:
        messages.error(request, 'Aucun document mis à jour disponible')
        return redirect('chat:documents_compare_select')

    # Créer le fichier texte à télécharger
    content = updated_doc['content']
    original_title = updated_doc.get('original_title', 'document')

    # Nettoyer le titre pour le nom de fichier
    safe_title = "".join([c for c in original_title if c.isalnum() or c in (' ', '-', '_')]).rstrip()
    filename = f"{safe_title}_updated.txt"

    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@login_required
def documents_update_download_pdf(request):
    """Télécharge le document mis à jour en format PDF"""
    from django.http import HttpResponse
    from .pdf_generator import PDFDocumentGenerator

    updated_doc = request.session.get('updated_document')

    if not updated_doc:
        messages.error(request, 'Aucun document mis à jour disponible')
        return redirect('chat:documents_compare_select')

    try:
        # Récupérer les données
        content = updated_doc['content']
        original_title = updated_doc.get('original_title', 'Document Mis à Jour')
        processing_time = updated_doc.get('processing_time', 0)

        # Métadonnées pour le PDF
        metadata = {
            'original_doc': original_title,
            'processing_time': processing_time,
        }

        # Générer le PDF
        pdf_generator = PDFDocumentGenerator()
        pdf_buffer = pdf_generator.generate_pdf(content, original_title, metadata)

        # Nettoyer le titre pour le nom de fichier
        safe_title = "".join([c for c in original_title if c.isalnum() or c in (' ', '-', '_')]).rstrip()
        filename = f"{safe_title}_updated.pdf"

        # Créer la réponse HTTP
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        messages.error(request, f'Erreur lors de la génération du PDF: {str(e)}')
        return redirect('chat:documents_compare_select')


@login_required
def documents_comparison_download_pdf(request):
    """Télécharge le rapport de comparaison en PDF"""
    from django.http import HttpResponse
    from .pdf_generator import PDFDocumentGenerator

    # Récupérer les données de comparaison depuis la session
    comparison_data = request.session.get('comparison_data')

    if not comparison_data:
        messages.error(request, 'Aucune comparaison disponible')
        return redirect('chat:documents_compare_select')

    try:
        # Générer le PDF
        pdf_generator = PDFDocumentGenerator()
        pdf_buffer = pdf_generator.generate_comparison_summary_pdf(comparison_data)

        # Nom du fichier
        filename = "comparaison_documents.pdf"

        # Créer la réponse HTTP
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        messages.error(request, f'Erreur lors de la génération du PDF: {str(e)}')
        return redirect('chat:documents_compare_select')


@login_required
@require_POST
def documents_apply_changes(request):
    """Applique directement les changements du Document 2 au Document 1 (API)"""
    doc1_id = request.POST.get('doc1_id')
    doc2_id = request.POST.get('doc2_id')

    if not doc1_id or not doc2_id:
        return JsonResponse({
            'success': False,
            'error': 'IDs de documents manquants'
        }, status=400)

    try:
        doc1 = Document.objects.get(pk=doc1_id, user=request.user)
        doc2 = Document.objects.get(pk=doc2_id, user=request.user)

        # Appliquer les changements au Document 1
        result = DocumentUpdateService.apply_changes_to_document(doc1, doc2)

        if result.get('success'):
            # Rafraîchir le document pour obtenir les nouvelles données
            doc1.refresh_from_db()

            # Stocker l'ID du document mis à jour dans la session pour le téléchargement
            request.session['updated_document_id'] = doc1.id

            return JsonResponse({
                'success': True,
                'message': result['message'],
                'processing_time': result['processing_time'],
                'updated_word_count': result['updated_word_count'],
                'document_title': doc1.title,
                'document_id': doc1.id,
                'file_modified': result.get('file_modified', False),
                'has_file': bool(doc1.file)
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Erreur inconnue')
            }, status=500)

    except Document.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Document non trouvé'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def documents_download_updated(request, doc_id):
    """Télécharge le document mis à jour en TXT"""
    try:
        document = Document.objects.get(pk=doc_id, user=request.user)

        # Récupérer le contenu
        content = DocumentComparisonService._get_document_content(document)

        # Créer la réponse HTTP
        response = HttpResponse(content, content_type='text/plain; charset=utf-8')
        filename = f"{document.title}_mis_a_jour.txt"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Document.DoesNotExist:
        messages.error(request, 'Document non trouvé')
        return redirect('chat:documents_compare_select')
    except Exception as e:
        messages.error(request, f'Erreur lors du téléchargement: {str(e)}')
        return redirect('chat:documents_compare_select')


@login_required
def documents_download_updated_pdf(request, doc_id):
    """Télécharge le document mis à jour en PDF"""
    from django.http import HttpResponse
    from .pdf_generator import PDFDocumentGenerator

    try:
        document = Document.objects.get(pk=doc_id, user=request.user)

        # Récupérer le contenu
        content = DocumentComparisonService._get_document_content(document)

        # Générer le PDF
        pdf_generator = PDFDocumentGenerator()
        pdf_buffer = pdf_generator.generate_clean_document_pdf(
            title=document.title,
            content=content
        )

        # Nom du fichier
        filename = f"{document.title}_mis_a_jour.pdf"

        # Créer la réponse HTTP
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Document.DoesNotExist:
        messages.error(request, 'Document non trouvé')
        return redirect('chat:documents_compare_select')
    except Exception as e:
        messages.error(request, f'Erreur lors de la génération du PDF: {str(e)}')
        return redirect('chat:documents_compare_select')


@login_required
def documents_download_original_file(request, doc_id):
    """Télécharge le fichier original modifié (Word, PDF, etc.) avec structure préservée"""
    import os
    from django.http import FileResponse

    try:
        document = Document.objects.get(pk=doc_id, user=request.user)

        # Vérifier que le document a un fichier
        if not document.file:
            messages.error(request, 'Ce document n\'a pas de fichier associé')
            return redirect('chat:documents_compare_select')

        # Vérifier que le fichier existe
        if not os.path.exists(document.file.path):
            messages.error(request, 'Le fichier du document n\'existe pas')
            return redirect('chat:documents_compare_select')

        # Déterminer le type MIME
        file_ext = os.path.splitext(document.file.name)[1].lower()
        content_types = {
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
        }
        content_type = content_types.get(file_ext, 'application/octet-stream')

        # Créer la réponse avec le fichier
        response = FileResponse(
            open(document.file.path, 'rb'),
            content_type=content_type
        )

        # Nom de fichier pour le téléchargement
        filename = os.path.basename(document.file.name)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Document.DoesNotExist:
        messages.error(request, 'Document non trouvé')
        return redirect('chat:documents_compare_select')
    except Exception as e:
        messages.error(request, f'Erreur lors du téléchargement: {str(e)}')
        return redirect('chat:documents_compare_select')
