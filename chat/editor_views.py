# FICHIER: chat/editor_views.py
# VUES POUR L'ÉDITEUR DE DOCUMENTS
# ============================================
# Gestion de l'éditeur de documents style Word/Canva

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.utils import timezone
from documents.models import Document, DocumentContent
from .models import Conversation, Message, GeneratedFile
from .advanced_pdf_service import AdvancedPDFExtractor, PDFToEditableConverter
import json
import os
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import ImageReader
from PIL import Image
import base64
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from documents.models import Document, DocumentContent


@login_required
@require_http_methods(["GET"])
def document_editor(request, document_id):
    """
    Vue principale de l'éditeur de documents.
    Charge un document et affiche l'interface d'édition complète.

    Args:
        document_id: ID du document à éditer
    """
    document = get_object_or_404(Document, id=document_id, user=request.user)

    # Vérifier si le document a un fichier PDF
    if not document.file:
        return render(request, 'chat/editor_error.html', {
            'error': 'Ce document ne possède pas de fichier PDF.',
            'document': document
        })

    context = {
        'document': document,
        'page_title': f'Éditeur - {document.title}'
    }

    return render(request, 'chat/document_editor.html', context)


@login_required
@require_http_methods(["GET"])
def conversation_editor(request, conversation_id, document_id=None):
    """
    Vue de l'éditeur intégré dans une conversation.
    Permet d'éditer un document dans le contexte d'une conversation avec l'agent IA.

    Args:
        conversation_id: ID de la conversation
        document_id: ID du document à éditer (optionnel, prend le premier si non spécifié)
    """
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)

    # Déterminer quel document éditer
    if document_id:
        document = get_object_or_404(Document, id=document_id, user=request.user)
        # Vérifier que le document est attaché à la conversation
        if document not in conversation.documents.all():
            return render(request, 'chat/editor_error.html', {
                'error': 'Ce document n\'est pas associé à cette conversation.',
                'conversation': conversation
            })
    else:
        # Prendre le premier document de la conversation
        document = conversation.documents.first()
        if not document:
            return render(request, 'chat/editor_error.html', {
                'error': 'Cette conversation ne contient aucun document.',
                'conversation': conversation
            })

    # Récupérer tous les documents de la conversation pour la navigation
    all_documents = conversation.documents.all()

    # Récupérer les messages récents
    recent_messages = Message.objects.filter(conversation=conversation).order_by('-created_at')[:10]

    context = {
        'conversation': conversation,
        'document': document,
        'all_documents': all_documents,
        'recent_messages': recent_messages,
        'page_title': f'{conversation.title} - Éditeur'
    }

    return render(request, 'chat/conversation_editor.html', context)


@require_POST
def extract_document_content(request, document_id):
    """Extract document content in specified format"""
    try:
        document = Document.objects.get(id=document_id)
        format_type = request.POST.get('format', 'quill')
        
        # Get DocumentContent
        try:
            doc_content = DocumentContent.objects.get(document=document)
            pdf_structure = doc_content.pdf_structure
        except DocumentContent.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Document content not found. Please re-upload the document.'
            })
        
        if format_type == 'fabric':
            # Check if we have an editor draft (saved content)
            if pdf_structure and isinstance(pdf_structure, dict):
                if 'editor_draft' in pdf_structure and pdf_structure['editor_draft'].get('content_type') == 'fabric':
                    # Return saved Fabric content
                    return JsonResponse({
                        'success': True,
                        'content': pdf_structure['editor_draft']['content']
                    })
                elif 'pages' in pdf_structure:
                    # Return original PDF structure with pages
                    return JsonResponse({
                        'success': True,
                        'content': pdf_structure
                    })
                else:
                    # No valid structure
                    return JsonResponse({
                        'success': False,
                        'error': 'No valid PDF structure available'
                    })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'No PDF structure available'
                })
        
        else:  # quill format
            # Check for saved Quill content first
            if pdf_structure and isinstance(pdf_structure, dict):
                if 'editor_draft' in pdf_structure and pdf_structure['editor_draft'].get('content_type') == 'quill':
                    return JsonResponse({
                        'success': True,
                        'content': pdf_structure['editor_draft']['content']
                    })
                elif 'editor_type' in pdf_structure and pdf_structure['editor_type'] == 'quill':
                    return JsonResponse({
                        'success': True,
                        'content': pdf_structure.get('content', {'ops': []})
                    })
            
            # Convert text to Quill Delta format
            text_content = doc_content.raw_text or doc_content.processed_text or ''
            
            delta_ops = []
            if text_content:
                lines = text_content.split('\n')
                for line in lines:
                    if line.strip():
                        delta_ops.append({'insert': line})
                        delta_ops.append({'insert': '\n'})
            
            return JsonResponse({
                'success': True,
                'content': {'ops': delta_ops}
            })
            
    except Document.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Document not found'
        })
    except Exception as e:
        print(f"❌ Error extracting document: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@require_POST
def save_document_changes(request, document_id):
    """Save document changes from editor"""
    try:
        document = Document.objects.get(id=document_id)
        content_type = request.POST.get('content_type', 'quill')
        content_data = request.POST.get('content_data', '{}')
        conversation_id = request.POST.get('conversation_id')
        
        # Parse the content
        try:
            content = json.loads(content_data)
        except json.JSONDecodeError as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid JSON: {str(e)}'
            })
        
        # Get or create DocumentContent
        doc_content, created = DocumentContent.objects.get_or_create(
            document=document,
            defaults={
                'raw_text': '',
                'processed_text': ''
            }
        )
        
        # Save based on content type
        if content_type == 'fabric':
            # Save Fabric.js canvas data
            doc_content.pdf_structure = content
            
            # Extract text from Fabric objects for search
            text_parts = []
            if 'objects' in content:
                for obj in content['objects']:
                    if obj.get('type') in ['text', 'textbox', 'i-text']:
                        text_parts.append(obj.get('text', ''))
            
            doc_content.processed_text = '\n'.join(text_parts)
            
        else:  # quill
            # Save Quill Delta format
            # Store as JSON in pdf_structure
            doc_content.pdf_structure = {
                'editor_type': 'quill',
                'content': content
            }
            
            # Extract plain text for search
            text_parts = []
            if 'ops' in content:
                for op in content['ops']:
                    if isinstance(op.get('insert'), str):
                        text_parts.append(op['insert'])
            
            doc_content.processed_text = ''.join(text_parts)
        
        doc_content.save()
        
        # Mark document as modified
        document.status = 'completed'
        document.save()
        
        # If this is part of a conversation, create a generated file record
        if conversation_id:
            try:
                from chat.models import Conversation, GeneratedFile
                conversation = Conversation.objects.get(id=conversation_id)
                
                # Create or update generated file record
                gen_file, created = GeneratedFile.objects.get_or_create(
                    conversation=conversation,
                    title=f"{document.title} (modifié)",
                    defaults={
                        'file_type': 'document_edit',
                        'content': content_data
                    }
                )
                
                if not created:
                    gen_file.content = content_data
                    gen_file.save()
                    
            except Exception as e:
                print(f"Warning: Could not create GeneratedFile: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Document sauvegardé avec succès'
        })
        
    except Document.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Document not found'
        })
    except Exception as e:
        print(f"❌ Error saving document: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def export_document(request, document_id):
    """
    API pour exporter un document dans différents formats.

    Args:
        document_id: ID du document à exporter

    Returns:
        Fichier dans le format demandé
    """
    document = get_object_or_404(Document, id=document_id, user=request.user)

    try:
        export_format = request.POST.get('format', 'pdf')
        content_data = request.POST.get('content_data')
        content_type = request.POST.get('content_type', 'quill')

        if not content_data:
            return JsonResponse({
                'success': False,
                'error': 'Aucune donnée de contenu fournie.'
            }, status=400)

        content = json.loads(content_data)

        if export_format == 'pdf':
            # Exporter en PDF
            pdf_buffer = _generate_pdf_from_content(content, content_type)
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{document.title}.pdf"'
            return response

        elif export_format == 'html':
            # Exporter en HTML
            html_content = _generate_html_from_content(content, content_type)
            response = HttpResponse(html_content, content_type='text/html')
            response['Content-Disposition'] = f'attachment; filename="{document.title}.html"'
            return response

        elif export_format == 'txt':
            # Exporter en texte brut
            text_content = _generate_text_from_content(content, content_type)
            response = HttpResponse(text_content, content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="{document.title}.txt"'
            return response

        else:
            return JsonResponse({
                'success': False,
                'error': f'Format d\'export non supporté: {export_format}'
            }, status=400)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de l\'export: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def auto_save_document(request, document_id):
    """
    API pour la sauvegarde automatique (draft).
    Sauvegarde l'état actuel sans créer de nouvelle version.

    Args:
        document_id: ID du document

    Returns:
        JSON de confirmation
    """
    document = get_object_or_404(Document, id=document_id, user=request.user)

    try:
        content_data = request.POST.get('content_data')
        content_type = request.POST.get('content_type', 'quill')

        if not content_data:
            return JsonResponse({
                'success': False,
                'error': 'Aucune donnée fournie.'
            }, status=400)

        # Sauvegarder dans le DocumentContent comme draft
        doc_content, created = DocumentContent.objects.get_or_create(
            document=document,
            defaults={'raw_text': '', 'processed_text': ''}
        )

        # Stocker le draft dans pdf_structure (champ JSON existant)
        if not doc_content.pdf_structure:
            doc_content.pdf_structure = {}

        # Conserver la structure PDF originale et ajouter le draft
        if not isinstance(doc_content.pdf_structure, dict):
            doc_content.pdf_structure = {}

        doc_content.pdf_structure['editor_draft'] = {
            'content': json.loads(content_data),
            'content_type': content_type,
            'saved_at': timezone.now().isoformat()
        }
        doc_content.save()

        return JsonResponse({
            'success': True,
            'message': 'Sauvegarde automatique effectuée',
            'saved_at': timezone.now().isoformat()
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Erreur lors de la sauvegarde automatique: {str(e)}'
        }, status=500)


# Fonctions utilitaires privées

def _generate_pdf_from_content(content: dict, content_type: str) -> BytesIO:
    """
    Génère un PDF à partir du contenu de l'éditeur.

    Args:
        content: Contenu de l'éditeur
        content_type: Type de contenu ('quill', 'fabric', etc.)

    Returns:
        Buffer contenant le PDF
    """
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y_position = height - 50

    if content_type == 'quill':
        # Traiter le contenu Quill Delta
        ops = content.get('ops', [])

        for op in ops:
            insert = op.get('insert', '')
            attributes = op.get('attributes', {})

            if isinstance(insert, str):
                # Texte
                for line in insert.split('\n'):
                    if line.strip():
                        # Appliquer les styles
                        font_size = 12
                        if attributes.get('size'):
                            try:
                                font_size = int(attributes['size'].replace('px', ''))
                            except:
                                pass

                        # Définir la police
                        if attributes.get('bold') and attributes.get('italic'):
                            c.setFont('Helvetica-BoldOblique', font_size)
                        elif attributes.get('bold'):
                            c.setFont('Helvetica-Bold', font_size)
                        elif attributes.get('italic'):
                            c.setFont('Helvetica-Oblique', font_size)
                        else:
                            c.setFont('Helvetica', font_size)

                        # Couleur
                        if attributes.get('color'):
                            # Convertir hex en RGB
                            color = attributes['color'].lstrip('#')
                            r, g, b = tuple(int(color[i:i+2], 16) / 255 for i in (0, 2, 4))
                            c.setFillColorRGB(r, g, b)
                        else:
                            c.setFillColorRGB(0, 0, 0)

                        # Écrire le texte
                        c.drawString(50, y_position, line)

                    y_position -= 20

                    # Nouvelle page si nécessaire
                    if y_position < 50:
                        c.showPage()
                        y_position = height - 50

            elif isinstance(insert, dict) and 'image' in insert:
                # Image
                try:
                    img_data = insert['image']
                    if img_data.startswith('data:image'):
                        # Extraire les données base64
                        img_data = img_data.split(',')[1]
                        img_bytes = base64.b64decode(img_data)
                        img = Image.open(BytesIO(img_bytes))

                        # Redimensionner si nécessaire
                        max_width = width - 100
                        img_width, img_height = img.size

                        if img_width > max_width:
                            ratio = max_width / img_width
                            img_width = max_width
                            img_height = int(img_height * ratio)

                        # Dessiner l'image
                        img_reader = ImageReader(img)
                        c.drawImage(img_reader, 50, y_position - img_height,
                                  width=img_width, height=img_height)

                        y_position -= (img_height + 20)

                        # Nouvelle page si nécessaire
                        if y_position < 50:
                            c.showPage()
                            y_position = height - 50
                except Exception as e:
                    print(f"Erreur lors de l'ajout de l'image: {e}")

    elif content_type == 'fabric':
        # Traiter le contenu Fabric.js
        objects = content.get('objects', [])

        # Trier les objets par position verticale (top) pour l'ordre de rendu
        sorted_objects = sorted(objects, key=lambda obj: obj.get('top', 0))

        for obj in sorted_objects:
            obj_type = obj.get('type', '')

            if obj_type == 'text':
                # Texte éditable (IText/Text)
                text = obj.get('text', '')
                left = obj.get('left', 50)
                top = obj.get('top', 0)
                font_size = obj.get('fontSize', 12)
                font_weight = obj.get('fontWeight', 'normal')
                font_style = obj.get('fontStyle', 'normal')
                fill = obj.get('fill', '#000000')

                # Convertir la position Fabric (top-left origin) en position PDF (bottom-left origin)
                pdf_y = height - top - font_size

                # Définir la police
                if font_weight == 'bold' and font_style == 'italic':
                    c.setFont('Helvetica-BoldOblique', font_size)
                elif font_weight == 'bold':
                    c.setFont('Helvetica-Bold', font_size)
                elif font_style == 'italic':
                    c.setFont('Helvetica-Oblique', font_size)
                else:
                    c.setFont('Helvetica', font_size)

                # Couleur du texte
                if fill.startswith('#'):
                    color = fill.lstrip('#')
                    try:
                        r, g, b = tuple(int(color[i:i+2], 16) / 255 for i in (0, 2, 4))
                        c.setFillColorRGB(r, g, b)
                    except:
                        c.setFillColorRGB(0, 0, 0)
                elif fill.startswith('rgb'):
                    # Format rgb(r, g, b) ou rgba(r, g, b, a)
                    try:
                        rgb_values = fill.replace('rgb(', '').replace('rgba(', '').replace(')', '').split(',')
                        r, g, b = int(rgb_values[0])/255, int(rgb_values[1])/255, int(rgb_values[2])/255
                        c.setFillColorRGB(r, g, b)
                    except:
                        c.setFillColorRGB(0, 0, 0)
                else:
                    c.setFillColorRGB(0, 0, 0)

                # Écrire le texte (gérer les lignes multiples)
                for line in text.split('\n'):
                    if pdf_y > 20:  # Vérifier qu'on est dans les limites
                        c.drawString(left, pdf_y, line)
                        pdf_y -= (font_size + 2)

            elif obj_type == 'rect':
                # Rectangle
                left = obj.get('left', 0)
                top = obj.get('top', 0)
                rect_width = obj.get('width', 100)
                rect_height = obj.get('height', 100)
                fill = obj.get('fill', 'transparent')
                stroke = obj.get('stroke', '#000000')
                stroke_width = obj.get('strokeWidth', 1)

                # Convertir position
                pdf_y = height - top - rect_height

                # Définir la couleur de remplissage
                if fill and fill != 'transparent' and not fill.startswith('rgba('):
                    if fill.startswith('#'):
                        color = fill.lstrip('#')
                        try:
                            r, g, b = tuple(int(color[i:i+2], 16) / 255 for i in (0, 2, 4))
                            c.setFillColorRGB(r, g, b)
                        except:
                            pass

                # Définir la couleur de bordure
                if stroke and stroke != 'transparent':
                    if stroke.startswith('#'):
                        color = stroke.lstrip('#')
                        try:
                            r, g, b = tuple(int(color[i:i+2], 16) / 255 for i in (0, 2, 4))
                            c.setStrokeColorRGB(r, g, b)
                        except:
                            pass
                    c.setLineWidth(stroke_width)

                # Dessiner le rectangle
                if fill and fill != 'transparent' and not fill.startswith('rgba('):
                    c.rect(left, pdf_y, rect_width, rect_height, fill=1, stroke=1 if stroke else 0)
                else:
                    c.rect(left, pdf_y, rect_width, rect_height, fill=0, stroke=1 if stroke else 0)

            elif obj_type == 'line':
                # Ligne
                x1 = obj.get('x1', 0)
                y1 = obj.get('y1', 0)
                x2 = obj.get('x2', 100)
                y2 = obj.get('y2', 0)
                left = obj.get('left', 0)
                top = obj.get('top', 0)
                stroke = obj.get('stroke', '#000000')
                stroke_width = obj.get('strokeWidth', 1)

                # Convertir positions
                pdf_y1 = height - (top + y1)
                pdf_y2 = height - (top + y2)

                # Couleur de la ligne
                if stroke and stroke.startswith('#'):
                    color = stroke.lstrip('#')
                    try:
                        r, g, b = tuple(int(color[i:i+2], 16) / 255 for i in (0, 2, 4))
                        c.setStrokeColorRGB(r, g, b)
                    except:
                        pass

                c.setLineWidth(stroke_width)
                c.line(left + x1, pdf_y1, left + x2, pdf_y2)

            elif obj_type == 'image':
                # Image
                try:
                    img_src = obj.get('src', '')
                    left = obj.get('left', 50)
                    top = obj.get('top', 0)
                    img_width = obj.get('width', 100)
                    img_height = obj.get('height', 100)

                    # Convertir position
                    pdf_y = height - top - img_height

                    if img_src.startswith('data:image'):
                        # Extraire les données base64
                        img_data = img_src.split(',')[1]
                        img_bytes = base64.b64decode(img_data)
                        img = Image.open(BytesIO(img_bytes))

                        # Dessiner l'image
                        img_reader = ImageReader(img)
                        c.drawImage(img_reader, left, pdf_y, width=img_width, height=img_height)
                except Exception as e:
                    print(f"Erreur lors de l'ajout de l'image Fabric: {e}")

    c.save()
    buffer.seek(0)
    return buffer


def _generate_html_from_content(content: dict, content_type: str) -> str:
    """
    Génère du HTML à partir du contenu de l'éditeur.

    Args:
        content: Contenu de l'éditeur
        content_type: Type de contenu

    Returns:
        Contenu HTML
    """
    html_parts = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '<meta charset="UTF-8">',
        '<title>Document</title>',
        '<style>body { font-family: Arial, sans-serif; padding: 20px; }</style>',
        '</head>',
        '<body>'
    ]

    if content_type == 'quill':
        ops = content.get('ops', [])

        for op in ops:
            insert = op.get('insert', '')
            attributes = op.get('attributes', {})

            if isinstance(insert, str):
                text = insert.replace('\n', '<br>')

                # Appliquer les styles
                styles = []
                if attributes.get('bold'):
                    text = f'<strong>{text}</strong>'
                if attributes.get('italic'):
                    text = f'<em>{text}</em>'
                if attributes.get('color'):
                    styles.append(f"color: {attributes['color']}")
                if attributes.get('size'):
                    styles.append(f"font-size: {attributes['size']}")

                if styles:
                    text = f'<span style="{"; ".join(styles)}">{text}</span>'

                html_parts.append(f'<p>{text}</p>')

            elif isinstance(insert, dict) and 'image' in insert:
                html_parts.append(f'<img src="{insert["image"]}" />')

    elif content_type == 'fabric':
        # Traiter le contenu Fabric.js
        objects = content.get('objects', [])

        # Trier les objets par position verticale
        sorted_objects = sorted(objects, key=lambda obj: obj.get('top', 0))

        for obj in sorted_objects:
            obj_type = obj.get('type', '')

            if obj_type == 'text':
                text = obj.get('text', '').replace('\n', '<br>')
                font_size = obj.get('fontSize', 12)
                font_weight = obj.get('fontWeight', 'normal')
                font_style = obj.get('fontStyle', 'normal')
                fill = obj.get('fill', '#000000')

                styles = [f"font-size: {font_size}px"]
                if font_weight == 'bold':
                    styles.append('font-weight: bold')
                if font_style == 'italic':
                    styles.append('font-style: italic')
                if fill:
                    styles.append(f'color: {fill}')

                style_str = '; '.join(styles)
                html_parts.append(f'<p style="{style_str}">{text}</p>')

            elif obj_type == 'image':
                img_src = obj.get('src', '')
                img_width = obj.get('width', 100)
                img_height = obj.get('height', 100)
                html_parts.append(f'<img src="{img_src}" width="{img_width}" height="{img_height}" />')

    html_parts.extend(['</body>', '</html>'])
    return '\n'.join(html_parts)


def _generate_text_from_content(content: dict, content_type: str) -> str:
    """
    Génère du texte brut à partir du contenu de l'éditeur.

    Args:
        content: Contenu de l'éditeur
        content_type: Type de contenu

    Returns:
        Contenu texte
    """
    text_parts = []

    if content_type == 'quill':
        ops = content.get('ops', [])

        for op in ops:
            insert = op.get('insert', '')

            if isinstance(insert, str):
                text_parts.append(insert)

    elif content_type == 'fabric':
        # Traiter le contenu Fabric.js
        objects = content.get('objects', [])

        # Trier les objets par position verticale
        sorted_objects = sorted(objects, key=lambda obj: obj.get('top', 0))

        for obj in sorted_objects:
            obj_type = obj.get('type', '')

            if obj_type == 'text':
                text = obj.get('text', '')
                text_parts.append(text)
                text_parts.append('\n')

    return ''.join(text_parts)
