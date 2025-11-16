"""
Service des outils de documents pour l'Agent Intelligent
Fournit les outils : compare, merge, generate_pdf, extract
"""
from typing import Dict, List, Optional
from django.core.files.base import ContentFile
from django.utils import timezone
import os

from .models import GeneratedFile, ConversationDocument
from documents.models import Document
from .services import DocumentComparisonService, DocumentUpdateService
from .pdf_generator import PDFDocumentGenerator


class DocumentToolsService:
    """
    Service fournissant les outils disponibles pour l'agent
    """

    @staticmethod
    def compare_documents(
        document_ids: List[int],
        comparison_type: str,
        conversation
    ) -> Dict:
        """
        Outil: Compare plusieurs documents

        Args:
            document_ids: Liste des IDs des documents à comparer
            comparison_type: Type de comparaison ('differences', 'similarities', 'full')
            conversation: Instance de Conversation

        Returns:
            Dict avec les résultats de la comparaison
        """
        print(f"[TOOL] compare_documents: {document_ids}, type={comparison_type}")

        try:
            if len(document_ids) < 2:
                return {
                    'success': False,
                    'error': 'Il faut au moins 2 documents pour faire une comparaison'
                }

            # Récupérer les documents
            documents = Document.objects.filter(id__in=document_ids)

            if documents.count() != len(document_ids):
                return {
                    'success': False,
                    'error': 'Certains documents sont introuvables'
                }

            # Pour l'instant, on compare seulement 2 documents
            if len(document_ids) > 2:
                return {
                    'success': False,
                    'error': 'La comparaison est limitée à 2 documents pour le moment'
                }

            doc1 = documents[0]
            doc2 = documents[1]

            # Utiliser le service de comparaison existant
            comparison_result = DocumentComparisonService.compare_documents(doc1, doc2)

            if not comparison_result.get('success'):
                return {
                    'success': False,
                    'error': comparison_result.get('error', 'Erreur lors de la comparaison')
                }

            comparison_data = comparison_result.get('comparison', {})

            # Générer un PDF de rapport de comparaison
            generated_file = DocumentToolsService._generate_comparison_pdf(
                doc1=doc1,
                doc2=doc2,
                comparison_data=comparison_data,
                conversation=conversation
            )

            # Construire le résultat
            result_text = f"Comparaison effectuée entre '{doc1.title}' et '{doc2.title}'.\n\n"

            if comparison_data.get('type') == 'llm':
                # Analyse du LLM
                analysis = comparison_data.get('analysis', '')
                result_text += f"Analyse détaillée :\n{analysis[:500]}..."
                if generated_file:
                    result_text += f"\n\nRapport complet disponible en téléchargement (ID: {generated_file.id})"
            else:
                # Analyse basique
                result_text += f"Similarité: {comparison_data.get('similarity', 0):.1f}%\n"
                result_text += f"Mots communs: {comparison_data.get('common_words', 0)}\n"

            return {
                'success': True,
                'comparison_type': comparison_type,
                'document_titles': [doc1.title, doc2.title],
                'analysis': comparison_data.get('analysis', ''),
                'similarity': comparison_data.get('similarity', 0),
                'result_text': result_text,
                'generated_file': generated_file
            }

        except Exception as e:
            print(f"[TOOL ERROR] compare_documents: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def merge_documents(
        source_doc_id: int,
        target_doc_id: int,
        merge_strategy: str,
        conversation
    ) -> Dict:
        """
        Outil: Fusionne deux documents

        Args:
            source_doc_id: ID du document source (avec modifications)
            target_doc_id: ID du document cible (à modifier)
            merge_strategy: Stratégie de fusion
            conversation: Instance de Conversation

        Returns:
            Dict avec le document fusionné
        """
        print(f"[TOOL] merge_documents: source={source_doc_id}, target={target_doc_id}, strategy={merge_strategy}")

        try:
            source_doc = Document.objects.get(id=source_doc_id)
            target_doc = Document.objects.get(id=target_doc_id)

            # Utiliser le service de mise à jour existant
            update_result = DocumentUpdateService.apply_changes_to_document(
                doc1=target_doc,
                doc2=source_doc
            )

            if not update_result.get('success'):
                return {
                    'success': False,
                    'error': update_result.get('error', 'Erreur lors de la fusion')
                }

            # Créer un fichier généré si un fichier a été modifié
            generated_file = None
            if update_result.get('file_modified'):
                # Le document cible a été modifié
                generated_file = GeneratedFile.objects.create(
                    conversation=conversation,
                    file=target_doc.file,
                    file_type='pdf' if target_doc.file.name.endswith('.pdf') else 'docx',
                    file_size=target_doc.file_size or 0,
                    title=f"{target_doc.title} (fusionné)",
                    description=f"Document fusionné de '{source_doc.title}' vers '{target_doc.title}'",
                    tool_used='merge'
                )
                generated_file.source_documents.add(source_doc, target_doc)

            result_text = f"Fusion effectuée : '{source_doc.title}' → '{target_doc.title}'\n"
            result_text += f"Stratégie : {merge_strategy}\n"
            result_text += f"Modifications appliquées : {update_result.get('modifications_count', 0)}\n"

            if generated_file:
                result_text += f"Document fusionné disponible en téléchargement (ID: {generated_file.id})"

            return {
                'success': True,
                'source_title': source_doc.title,
                'target_title': target_doc.title,
                'merge_strategy': merge_strategy,
                'modifications_count': update_result.get('modifications_count', 0),
                'result_text': result_text,
                'generated_file': generated_file
            }

        except Document.DoesNotExist:
            return {
                'success': False,
                'error': 'Un ou plusieurs documents sont introuvables'
            }
        except Exception as e:
            print(f"[TOOL ERROR] merge_documents: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def generate_pdf_document(
        title: str,
        content: str,
        template: str,
        source_docs: List[int],
        conversation
    ) -> Dict:
        """
        Outil: Génère un document PDF personnalisé

        Args:
            title: Titre du document
            content: Contenu (peut inclure du markdown)
            template: Type de template
            source_docs: IDs des documents sources
            conversation: Instance de Conversation

        Returns:
            Dict avec le fichier PDF généré
        """
        print(f"[TOOL] generate_pdf_document: title='{title}', template={template}")

        try:
            # Générer le PDF
            generator = PDFDocumentGenerator()
            pdf_buffer = generator.generate_simple_pdf(
                title=title,
                content=content
            )

            # Sauvegarder le fichier
            filename = f"{title.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            generated_file = GeneratedFile.objects.create(
                conversation=conversation,
                file_type='pdf',
                file_size=len(pdf_buffer.getvalue()),
                title=title,
                description=f"Document PDF généré avec template '{template}'",
                tool_used='generate',
                generation_params={
                    'template': template,
                    'content_length': len(content)
                }
            )

            # Attacher le fichier
            generated_file.file.save(
                filename,
                ContentFile(pdf_buffer.getvalue()),
                save=True
            )

            # Attacher les documents sources
            if source_docs:
                docs = Document.objects.filter(id__in=source_docs)
                generated_file.source_documents.add(*docs)

            result_text = f"Document PDF '{title}' généré avec succès.\n"
            result_text += f"Template utilisé : {template}\n"
            result_text += f"Taille : {generated_file.file_size} bytes\n"
            result_text += f"Disponible en téléchargement (ID: {generated_file.id})"

            return {
                'success': True,
                'title': title,
                'template': template,
                'file_size': generated_file.file_size,
                'result_text': result_text,
                'generated_file': generated_file
            }

        except Exception as e:
            print(f"[TOOL ERROR] generate_pdf_document: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def _generate_comparison_pdf(
        doc1: Document,
        doc2: Document,
        comparison_data: Dict,
        conversation
    ) -> Optional[GeneratedFile]:
        """
        Génère un PDF de rapport de comparaison
        """
        try:
            generator = PDFDocumentGenerator()

            # Construire le contenu du rapport
            content = f"""RAPPORT DE COMPARAISON

Document 1: {doc1.title}
Document 2: {doc2.title}
Date: {timezone.now().strftime('%d/%m/%Y %H:%M')}

---

"""

            if comparison_data.get('type') == 'llm':
                content += comparison_data.get('analysis', '')
            else:
                content += f"""ANALYSE BASIQUE

Similarité globale: {comparison_data.get('similarity', 0):.1f}%

Statistiques:
- Mots communs: {comparison_data.get('common_words', 0)}
- Mots uniques au Document 1: {comparison_data.get('unique_words_doc1', 0)}
- Mots uniques au Document 2: {comparison_data.get('unique_words_doc2', 0)}
"""

            # Générer le PDF
            pdf_buffer = generator.generate_simple_pdf(
                title=f"Comparaison: {doc1.title} vs {doc2.title}",
                content=content
            )

            # Sauvegarder
            filename = f"Comparaison_{doc1.id}_{doc2.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            generated_file = GeneratedFile.objects.create(
                conversation=conversation,
                file_type='pdf',
                file_size=len(pdf_buffer.getvalue()),
                title=f"Comparaison: {doc1.title} vs {doc2.title}",
                description=f"Rapport de comparaison entre {doc1.title} et {doc2.title}",
                tool_used='compare'
            )

            generated_file.file.save(
                filename,
                ContentFile(pdf_buffer.getvalue()),
                save=True
            )

            generated_file.source_documents.add(doc1, doc2)

            print(f"[TOOL] Rapport de comparaison PDF généré: {filename}")

            return generated_file

        except Exception as e:
            print(f"[TOOL ERROR] _generate_comparison_pdf: {e}")
            return None

    @staticmethod
    def answer_question(
        question: str,
        document_ids: List[int],
        conversation: 'Conversation'
    ) -> Dict:
        """Répond à une question en se basant sur les documents spécifiés"""
        print(f"[TOOL] answer_question: '{question}', docs={document_ids}")
        
        # Si aucun document spécifié, utiliser tous les documents de la conversation
        if not document_ids:
            document_ids = list(conversation.documents.values_list('id', flat=True))
        
        if not document_ids:
            return {
                'success': False,
                'error': 'Aucun document disponible pour répondre à la question'
            }
        
        # Construire le contexte à partir des documents
        context_parts = []
        
        for doc_id in document_ids:
            try:
                from documents.models import Document, DocumentContent
                doc = Document.objects.get(id=doc_id)
                
                # CETTE PARTIE EST CRITIQUE - Lire depuis DocumentContent
                try:
                    doc_content = DocumentContent.objects.get(document=doc)
                    content_text = doc_content.raw_text or doc_content.processed_text
                    
                    if content_text:
                        context_parts.append(f"Document: {doc.title}\n\n{content_text}")
                        print(f"[INFO] Document {doc_id} ({doc.title}) loaded: {len(content_text)} characters")
                    else:
                        print(f"[WARNING] Document {doc_id} ({doc.title}) has empty content")
                        
                except DocumentContent.DoesNotExist:
                    print(f"[WARNING] Aucun contenu trouvé pour le document {doc_id}: {doc.title}")
                    context_parts.append(f"Document: {doc.title}\n\nContenu non disponible - le document n'a pas été analysé.")
                    
            except Document.DoesNotExist:
                print(f"[ERROR] Document {doc_id} not found")
                continue
        
        if not context_parts:
            return {
                'success': False,
                'error': 'Aucun contenu de document disponible'
            }
        
        context = "\n\n---\n\n".join(context_parts)
        print(f"[INFO] Contexte total construit: {len(context)} caractères")
        
        # Appeler le LLM pour répondre à la question
        try:
            from groq import Groq
            from django.conf import settings
            
            client = Groq(api_key=settings.GROQ_API_KEY)
            
            system_prompt = """Tu es un assistant expert en analyse de documents pharmaceutiques et techniques.

    Ton rôle est de répondre aux questions en te basant UNIQUEMENT sur le contenu des documents fournis.

    RÈGLES IMPORTANTES :
    1. Si l'information est dans le document, fournis une réponse précise et détaillée
    2. Si l'information N'EST PAS dans le document, dis clairement : "Cette information n'est pas disponible dans le document fourni"
    3. CITE toujours tes sources en indiquant de quel document provient l'information
    4. Sois professionnel et précis dans tes réponses
    5. Pour les documents pharmaceutiques, fais attention aux détails techniques (dosages, spécifications, etc.)

    Format de réponse souhaité :
    - Commence par répondre directement à la question
    - Cite le document source
    - Ajoute des détails pertinents si disponibles"""

            user_prompt = f"""Voici les documents disponibles :

    {context}

    ---

    Question : {question}

    Réponds à cette question en te basant sur le contenu des documents ci-dessus."""

            print(f"[TOOL] Appel du LLM pour répondre à la question...")
            
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            answer = response.choices[0].message.content
            print(f"[TOOL] Réponse générée: {len(answer)} caractères")
            
            return {
                'success': True,
                'answer': answer,
                'documents_used': document_ids
            }
            
        except Exception as e:
            print(f"[TOOL ERROR] answer_question: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': f"Erreur lors de la génération de la réponse: {str(e)}"
            }
    
    @staticmethod
    def edit_document(
        document_id: int,
        find_text: str,
        replace_with: str,
        context: str,
        conversation
    ) -> Dict:
        """
        Outil: Modifie un élément spécifique dans un document en temps réel

        Args:
            document_id: ID du document à modifier
            find_text: Texte à trouver et remplacer
            replace_with: Nouveau texte
            context: Contexte optionnel pour localiser le texte
            conversation: Instance de Conversation

        Returns:
            Dict avec le fichier modifié
        """
        print(f"[TOOL] edit_document: doc_id={document_id}, find='{find_text}', replace='{replace_with}'")

        try:
            # Récupérer le document
            document = Document.objects.get(id=document_id)

            # Récupérer le contenu du document
            content = DocumentComparisonService._get_document_content(document)

            if not content:
                return {
                    'success': False,
                    'error': 'Impossible de lire le contenu du document'
                }

            # Créer un contenu modifié en remplaçant le texte
            modified_content = content.replace(find_text, replace_with)

            if modified_content == content:
                # Aucune modification n'a été effectuée
                return {
                    'success': False,
                    'error': f"Le texte '{find_text}' n'a pas été trouvé dans le document"
                }

            print(f"[TOOL] Texte trouvé et remplacé")

            # Récupérer la structure PDF si disponible
            pdf_structure = None
            if hasattr(document, 'content') and document.content.pdf_structure:
                pdf_structure = document.content.pdf_structure
                print(f"[INFO] Structure PDF récupérée: {pdf_structure.get('total_tables', 0)} tableau(x)")

            # Modifier aussi le brouillon de l'éditeur si disponible
            if pdf_structure and 'editor_draft' in pdf_structure:
                editor_draft = pdf_structure['editor_draft']
                content_data = editor_draft.get('content', {})
                content_type = editor_draft.get('content_type', 'quill')

                modifications_count = 0

                if content_type == 'quill' and 'ops' in content_data:
                    # Remplacer dans le format Quill
                    for op in content_data['ops']:
                        if 'insert' in op and isinstance(op['insert'], str):
                            if find_text in op['insert']:
                                op['insert'] = op['insert'].replace(find_text, replace_with)
                                modifications_count += 1

                    if modifications_count > 0:
                        editor_draft['saved_at'] = timezone.now().isoformat()
                        print(f"[INFO] {modifications_count} remplacement(s) effectué(s) dans l'éditeur Quill")

                elif content_type == 'fabric' and 'objects' in content_data:
                    # Remplacer dans le format Fabric.js

                    # DEBUG: Afficher tous les types d'objets disponibles
                    all_types = {}
                    for obj in content_data['objects']:
                        obj_type = obj.get('type', 'unknown')
                        all_types[obj_type] = all_types.get(obj_type, 0) + 1
                    print(f"[DEBUG] edit_document - Types d'objets: {all_types}")

                    # Les objets texte peuvent être de type 'text', 'textbox', 'i-text', 'IText'
                    text_types = ['text', 'textbox', 'i-text', 'IText']
                    text_objects = [obj for obj in content_data['objects'] if obj.get('type') in text_types]
                    print(f"[DEBUG] edit_document - Nombre d'objets texte: {len(text_objects)}")
                    print(f"[DEBUG] edit_document - Recherche de: '{find_text}'")
                    for i, obj in enumerate(text_objects[:10]):  # Afficher les 10 premiers
                        print(f"[DEBUG] edit_document - Texte {i+1}: '{obj.get('text', '')[:50]}'")

                    for obj in content_data['objects']:
                        if obj.get('type') in text_types:
                            text = obj.get('text', '').strip()
                            # Recherche flexible avec strip
                            if find_text.strip() in text:
                                obj['text'] = text.replace(find_text.strip(), replace_with)
                                modifications_count += 1

                    if modifications_count > 0:
                        editor_draft['saved_at'] = timezone.now().isoformat()
                        print(f"[INFO] {modifications_count} remplacement(s) effectué(s) dans l'éditeur Fabric")

                # Sauvegarder les modifications dans la base de données
                if modifications_count > 0:
                    # IMPORTANT: Forcer la détection de changement pour JSONField
                    document.content.pdf_structure = dict(document.content.pdf_structure)
                    document.content.save(update_fields=['pdf_structure'])
                    print(f"[INFO] Modifications sauvegardées dans la base de données")

            # Appliquer directement le remplacement à la structure PDF
            if pdf_structure:
                # Créer un dictionnaire de modifications simple
                modifications = {find_text: replace_with}
                print(f"[INFO] Application du remplacement: '{find_text}' → '{replace_with}'")

                # Utiliser PDFDocumentGenerator pour régénérer le PDF avec les modifications
                from chat.pdf_generator import PDFDocumentGenerator

                pdf_gen = PDFDocumentGenerator()
                pdf_buffer = pdf_gen.generate_pdf_from_structure(
                    title=f"{document.title} (modifié)",
                    pdf_structure=pdf_structure,
                    modifications=modifications
                )

                if not pdf_buffer:
                    return {
                        'success': False,
                        'error': 'Échec de la génération du PDF avec modifications'
                    }
            else:
                return {
                    'success': False,
                    'error': 'Structure PDF non disponible - impossible de préserver la mise en forme'
                }

            # Sauvegarder comme GeneratedFile
            from datetime import datetime
            from django.core.files.base import ContentFile

            filename = f"{document.title.replace('.pdf', '')}_edited_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            generated_file = GeneratedFile.objects.create(
                conversation=conversation,
                message=None,  # Pas de message spécifique
                file_type='pdf',
                title=f"✏️ {document.title} (modifié)",
                description=f"Modification: '{find_text}' → '{replace_with}'"
            )

            generated_file.file.save(filename, ContentFile(pdf_buffer.getvalue()), save=True)

            print(f"[TOOL] Document modifié sauvegardé: {filename}")

            return {
                'success': True,
                'document_id': document_id,
                'document_title': document.title,
                'find_text': find_text,
                'replace_with': replace_with,
                'modifications_applied': 1,
                'generated_file': generated_file,
                'file_url': generated_file.file.url,
                'result_text': f"✅ Modification effectuée avec succès dans '{document.title}'.\n"
                              f"Texte '{find_text}' remplacé par '{replace_with}'.\n"
                              f"Le document mis à jour est disponible au téléchargement."
            }

        except Document.DoesNotExist:
            return {
                'success': False,
                'error': f'Document avec ID {document_id} introuvable'
            }

        except Exception as e:
            print(f"[TOOL ERROR] edit_document: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def format_text(
        document_id: int,
        text_to_format: str,
        formatting_action: str,
        formatting_value: Optional[str],
        conversation
    ) -> Dict:
        """
        Outil: Modifie le formatage d'un texte spécifique dans l'éditeur

        Args:
            document_id: ID du document à modifier
            text_to_format: Texte dont on veut modifier le formatage
            formatting_action: Action à effectuer ('add_bold', 'remove_bold', 'add_italic', 'remove_italic',
                                                    'set_color', 'set_size', 'remove_all_formatting')
            formatting_value: Valeur pour l'action (ex: couleur hex, taille de police)
            conversation: Instance de Conversation

        Returns:
            Dict avec le résultat de la modification
        """
        print(f"[TOOL] format_text: doc_id={document_id}, text='{text_to_format}', action={formatting_action}")

        try:
            # Récupérer le document
            document = Document.objects.get(id=document_id)

            # Récupérer le DocumentContent
            from documents.models import DocumentContent
            doc_content = DocumentContent.objects.filter(document=document).first()

            if not doc_content:
                return {
                    'success': False,
                    'error': 'Contenu du document non trouvé'
                }

            # Récupérer le draft de l'éditeur
            print(f"[DEBUG] pdf_structure exists: {doc_content.pdf_structure is not None}")
            print(f"[DEBUG] pdf_structure type: {type(doc_content.pdf_structure)}")

            if not doc_content.pdf_structure or 'editor_draft' not in doc_content.pdf_structure:
                print(f"[DEBUG] pdf_structure keys: {list(doc_content.pdf_structure.keys()) if doc_content.pdf_structure else 'None'}")
                return {
                    'success': False,
                    'error': 'Aucun brouillon d\'éditeur trouvé. Veuillez d\'abord ouvrir le document dans l\'éditeur et attendre la sauvegarde automatique.'
                }

            editor_draft = doc_content.pdf_structure['editor_draft']
            content_data = editor_draft.get('content', {})
            content_type = editor_draft.get('content_type', 'quill')

            # Debug: Afficher la structure des données
            print(f"[DEBUG] editor_draft keys: {editor_draft.keys()}")
            print(f"[DEBUG] content_data type: {type(content_data)}")
            print(f"[DEBUG] content_type: {content_type}")
            print(f"[DEBUG] content_data: {str(content_data)[:500]}")

            modifications_count = 0

            # Gérer les deux formats: Quill et Fabric
            if content_type == 'quill':
                if not content_data or 'ops' not in content_data:
                    return {
                        'success': False,
                        'error': f'Format de contenu Quill invalide. Type: {type(content_data)}, Keys: {content_data.keys() if isinstance(content_data, dict) else "N/A"}'
                    }

                # Modifier le formatage dans le Delta (Quill)
                ops = content_data['ops']

                for op in ops:
                    if 'insert' in op and isinstance(op['insert'], str):
                        # Vérifier si ce segment contient le texte recherché
                        if text_to_format in op['insert']:
                            # Initialiser les attributs s'ils n'existent pas
                            if 'attributes' not in op:
                                op['attributes'] = {}

                            # Appliquer l'action de formatage
                            if formatting_action == 'remove_bold':
                                if 'bold' in op['attributes']:
                                    del op['attributes']['bold']
                                    modifications_count += 1

                            elif formatting_action == 'add_bold':
                                op['attributes']['bold'] = True
                                modifications_count += 1

                            elif formatting_action == 'remove_italic':
                                if 'italic' in op['attributes']:
                                    del op['attributes']['italic']
                                    modifications_count += 1

                            elif formatting_action == 'add_italic':
                                op['attributes']['italic'] = True
                                modifications_count += 1

                            elif formatting_action == 'set_color':
                                if formatting_value:
                                    op['attributes']['color'] = formatting_value
                                    modifications_count += 1

                            elif formatting_action == 'remove_color':
                                if 'color' in op['attributes']:
                                    del op['attributes']['color']
                                    modifications_count += 1

                        elif formatting_action == 'set_size':
                            if formatting_value:
                                op['attributes']['size'] = formatting_value
                                modifications_count += 1

                        elif formatting_action == 'remove_all_formatting':
                            op['attributes'] = {}
                            modifications_count += 1

                        # Nettoyer les attributs vides
                        if not op['attributes']:
                            del op['attributes']

            elif content_type == 'fabric':
                # Format Fabric.js (édition visuelle)
                if not content_data or 'objects' not in content_data:
                    return {
                        'success': False,
                        'error': f'Format de contenu Fabric invalide. Type: {type(content_data)}, Keys: {content_data.keys() if isinstance(content_data, dict) else "N/A"}'
                    }

                # Modifier le formatage dans les objets Fabric
                objects = content_data['objects']

                # DEBUG: Afficher tous les types d'objets disponibles
                all_types = {}
                for obj in objects:
                    obj_type = obj.get('type', 'unknown')
                    all_types[obj_type] = all_types.get(obj_type, 0) + 1
                print(f"[DEBUG] Types d'objets dans Fabric: {all_types}")

                # Les objets texte peuvent être de type 'text', 'textbox', 'i-text', 'IText'
                text_types = ['text', 'textbox', 'i-text', 'IText']
                text_objects = [obj for obj in objects if obj.get('type') in text_types]
                print(f"[DEBUG] Nombre d'objets texte dans Fabric: {len(text_objects)}")
                print(f"[DEBUG] Recherche de: '{text_to_format}'")
                for i, obj in enumerate(text_objects[:10]):  # Afficher les 10 premiers
                    print(f"[DEBUG] Texte {i+1}: '{obj.get('text', '')[:50]}'")

                for obj in objects:
                    # Ne traiter que les objets texte (tous types)
                    if obj.get('type') in text_types:
                        text = obj.get('text', '').strip()  # Enlever les espaces

                        # Recherche flexible: vérifier si le texte contient le texte recherché
                        # (avec strip pour ignorer les espaces en début/fin)
                        if text_to_format.strip() in text:
                            # Appliquer l'action de formatage
                            if formatting_action == 'remove_bold':
                                if obj.get('fontWeight') == 'bold':
                                    obj['fontWeight'] = 'normal'
                                    modifications_count += 1

                            elif formatting_action == 'add_bold':
                                obj['fontWeight'] = 'bold'
                                modifications_count += 1

                            elif formatting_action == 'remove_italic':
                                if obj.get('fontStyle') == 'italic':
                                    obj['fontStyle'] = 'normal'
                                    modifications_count += 1

                            elif formatting_action == 'add_italic':
                                obj['fontStyle'] = 'italic'
                                modifications_count += 1

                            elif formatting_action == 'set_color':
                                if formatting_value:
                                    obj['fill'] = formatting_value
                                    modifications_count += 1

                            elif formatting_action == 'remove_color':
                                obj['fill'] = '#000000'  # Noir par défaut
                                modifications_count += 1

                            elif formatting_action == 'set_size':
                                if formatting_value:
                                    try:
                                        obj['fontSize'] = float(formatting_value)
                                        modifications_count += 1
                                    except ValueError:
                                        pass

                            elif formatting_action == 'remove_all_formatting':
                                obj['fontWeight'] = 'normal'
                                obj['fontStyle'] = 'normal'
                                obj['fill'] = '#000000'
                                obj['fontSize'] = 12
                                modifications_count += 1

            if modifications_count == 0:
                return {
                    'success': False,
                    'error': f"Le texte '{text_to_format}' n'a pas été trouvé dans le document"
                }

            # Sauvegarder le contenu modifié
            doc_content.pdf_structure['editor_draft']['content'] = content_data
            doc_content.pdf_structure['editor_draft']['saved_at'] = timezone.now().isoformat()

            # IMPORTANT: Marquer le champ comme modifié pour forcer la sauvegarde (JSONField)
            from django.db.models import F
            doc_content.pdf_structure = dict(doc_content.pdf_structure)  # Force la détection de changement
            doc_content.save(update_fields=['pdf_structure'])

            print(f"[TOOL] Formatage modifié: {modifications_count} occurrence(s)")
            print(f"[INFO] Contenu sauvegardé dans la base de données")

            # Créer un message descriptif
            action_descriptions = {
                'remove_bold': 'Gras retiré',
                'add_bold': 'Gras ajouté',
                'remove_italic': 'Italique retiré',
                'add_italic': 'Italique ajouté',
                'set_color': f'Couleur changée en {formatting_value}',
                'remove_color': 'Couleur retirée',
                'set_size': f'Taille changée en {formatting_value}',
                'remove_all_formatting': 'Tout formatage retiré'
            }

            action_desc = action_descriptions.get(formatting_action, formatting_action)

            return {
                'success': True,
                'document_id': document_id,
                'document_title': document.title,
                'text_formatted': text_to_format,
                'action': formatting_action,
                'modifications_count': modifications_count,
                'result_text': f"✅ {action_desc} sur '{text_to_format}' dans '{document.title}'.\n"
                              f"{modifications_count} occurrence(s) modifiée(s).\n"
                              f"Les changements sont visibles dans l'éditeur. Actualisez la page si nécessaire."
            }

        except Document.DoesNotExist:
            return {
                'success': False,
                'error': f'Document avec ID {document_id} introuvable'
            }

        except Exception as e:
            print(f"[TOOL ERROR] format_text: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e)
            }
