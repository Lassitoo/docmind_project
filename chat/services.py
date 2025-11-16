# FICHIER: chat/services.py
# SERVICES POUR LE CHAT ET LA GÉNÉRATION DE RÉPONSES
# ============================================

from typing import List, Dict, Tuple
from django.db.models import Q
from django.conf import settings
from .models import Conversation, Message, QueryContext
from documents.models import Document, DocumentChunk
from database_manager.models import ExternalDatabase
import time

# Import Groq
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class ContextRetrievalService:
    """
    Service pour récupérer le contexte pertinent pour répondre à une question
    """

    @staticmethod
    def retrieve_from_documents(query: str, documents: List[Document], top_k: int = 10) -> List[Dict]:
        """
        Récupère les segments de documents les plus pertinents
        Note: Version simplifiée avec recherche textuelle - à améliorer avec embeddings
        """
        contexts = []

        # Récupérer tous les chunks des documents sélectionnés
        chunks = DocumentChunk.objects.filter(
            document__in=documents
        ).select_related('document')

        print(f"[DEBUG] Nombre de chunks trouvés: {chunks.count()}")
        print(f"[DEBUG] Documents: {[doc.title for doc in documents]}")

        # Si pas de chunks, utiliser le contenu complet du document
        if not chunks.exists():
            print("[DEBUG] Pas de chunks trouvés, utilisation du contenu complet")
            for document in documents:
                try:
                    content = document.content
                    # Découper le texte en morceaux de ~1000 caractères
                    text = content.raw_text
                    chunk_size = 1000
                    for i in range(0, len(text), chunk_size):
                        chunk_text = text[i:i+chunk_size]
                        contexts.append({
                            'document': document,
                            'chunk': None,
                            'content': chunk_text,
                            'relevance_score': 0.5,  # Score par défaut
                            'page_number': None,
                            'chunk_index': i // chunk_size
                        })
                except Exception as e:
                    print(f"[DEBUG] Erreur récupération contenu: {e}")
                    continue
            return contexts[:top_k]

        # Recherche simple par mots-clés
        query_words = set(query.lower().split())

        for chunk in chunks:
            # Calculer un score de pertinence simple
            chunk_words = set(chunk.content.lower().split())
            common_words = query_words.intersection(chunk_words)
            relevance_score = len(common_words) / len(query_words) if query_words else 0

            if relevance_score > 0:
                contexts.append({
                    'document': chunk.document,
                    'chunk': chunk,
                    'content': chunk.content,
                    'relevance_score': relevance_score,
                    'page_number': chunk.page_number,
                    'chunk_index': chunk.chunk_index
                })

        # Si aucun contexte pertinent trouvé, retourner TOUS les chunks (pas juste top_k)
        if not contexts and chunks.exists():
            print("[DEBUG] Aucun contexte pertinent, retour de TOUS les chunks")
            for chunk in chunks:  # Tous les chunks, pas seulement top_k
                contexts.append({
                    'document': chunk.document,
                    'chunk': chunk,
                    'content': chunk.content,
                    'relevance_score': 0.3,  # Score bas
                    'page_number': chunk.page_number,
                    'chunk_index': chunk.chunk_index
                })

        # Trier par score de pertinence et limiter
        contexts.sort(key=lambda x: x['relevance_score'], reverse=True)
        return contexts[:top_k]

    @staticmethod
    def retrieve_from_database(query: str, external_db: ExternalDatabase) -> List[Dict]:
        """
        Récupère des informations depuis une base de données externe
        Note: Placeholder - nécessite implémentation avec SQLAlchemy
        """
        # TODO: Implémenter la connexion et requête à la base externe
        contexts = []

        # Pour l'instant, retourne une liste vide
        # Dans une vraie implémentation, on convertirait la question en SQL

        return contexts


class ResponseGeneratorService:
    """
    Service pour générer des réponses basées sur le contexte
    """

    @staticmethod
    def generate_simple_response(query: str, contexts: List[Dict]) -> str:
        """
        Génère une réponse simple basée sur le contexte
        Note: Version simplifiée - à remplacer par un vrai modèle LLM
        """
        if not contexts:
            return "Je n'ai pas trouvé d'informations pertinentes pour répondre à votre question."

        # Construire une réponse basique
        response = "Basé sur les documents fournis, voici ce que j'ai trouvé:\n\n"

        for i, context in enumerate(contexts[:3], 1):
            response += f"{i}. {context['content'][:200]}...\n\n"

        response += "\nCes informations proviennent de vos documents uploadés."

        return response

    @staticmethod
    def generate_llm_response(query: str, contexts: List[Dict], conversation_history: List[Dict] = None) -> str:
        """
        Génère une réponse avec un modèle LLM (Groq)
        """
        # Vérifier si Groq est disponible et configuré
        if not GROQ_AVAILABLE or not hasattr(settings, 'GROQ_API_KEY') or not settings.GROQ_API_KEY:
            return ResponseGeneratorService.generate_simple_response(query, contexts)

        try:
            # Initialiser le client Groq
            client = Groq(api_key=settings.GROQ_API_KEY)

            # Construction du contexte - utiliser TOUT le contexte disponible
            context_parts = []
            total_chars = 0
            max_context_chars = 15000  # Limite de caractères pour le contexte

            for ctx in contexts:
                doc_title = ctx.get('document').title if ctx.get('document') else 'N/A'
                content = ctx['content']

                # Ajouter le chunk si on ne dépasse pas la limite
                if total_chars + len(content) < max_context_chars:
                    context_parts.append(f"[Chunk {ctx.get('chunk_index', '?')} du document {doc_title}]\n{content}")
                    total_chars += len(content)
                else:
                    break

            context_text = "\n\n---\n\n".join(context_parts)
            print(f"[DEBUG Groq] Contexte total: {len(context_parts)} chunks, {total_chars} caractères")

            # Construction des messages
            messages = [
                {
                    "role": "system",
                    "content": "Tu es un assistant intelligent spécialisé dans l'analyse de documents. Réponds de manière précise et concise en français, en te basant uniquement sur le contexte fourni."
                },
                {
                    "role": "user",
                    "content": f"""Contexte provenant des documents:
{context_text}

Question de l'utilisateur: {query}

Réponds à la question en te basant sur le contexte fourni. Si l'information n'est pas dans le contexte, indique-le clairement."""
                }
            ]

            print(f"[DEBUG Groq] Appel à Groq avec modèle: {settings.GROQ_MODEL}")
            print(f"[DEBUG Groq] Longueur du contexte: {len(context_text)} caractères")

            # Appel à l'API Groq
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=2000  # Augmenté pour des réponses plus complètes
            )

            print(f"[DEBUG Groq] Réponse reçue avec succès")
            return response.choices[0].message.content

        except Exception as e:
            # En cas d'erreur, fallback sur la réponse simple
            print(f"[ERREUR Groq] Type: {type(e).__name__}")
            print(f"[ERREUR Groq] Message: {str(e)}")
            import traceback
            print(f"[ERREUR Groq] Traceback complet:")
            traceback.print_exc()
            return ResponseGeneratorService.generate_simple_response(query, contexts)


class DocumentUpdateService:
    """
    Service pour générer un document mis à jour basé sur les différences
    """

    @staticmethod
    def generate_updated_document(doc1: Document, doc2: Document, selected_changes: list = None) -> Dict:
        """
        Génère un document mis à jour en fusionnant les changements sélectionnés
        """
        start_time = time.time()

        try:
            # Récupérer le contenu des documents
            content1 = DocumentComparisonService._get_document_content(doc1)
            content2 = DocumentComparisonService._get_document_content(doc2)

            # Utiliser le LLM pour générer le document mis à jour
            updated_content = DocumentUpdateService._generate_with_llm(
                doc1.title, content1,
                doc2.title, content2,
                selected_changes
            )

            processing_time = time.time() - start_time

            return {
                'success': True,
                'updated_content': updated_content,
                'processing_time': processing_time,
                'original_doc': doc1.title,
                'reference_doc': doc2.title
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Erreur lors de la génération: {str(e)}'
            }

    @staticmethod
    def apply_changes_to_document(doc1: Document, doc2: Document) -> Dict:
        """
        Applique directement les changements du Document 2 au Document 1
        en conservant la mise en forme originale (tableaux, styles, mise en page)
        """
        start_time = time.time()

        try:
            from .document_modifier import DocumentModifierService
            from django.core.files.base import ContentFile
            import os

            # Récupérer le contenu des documents
            content1 = DocumentComparisonService._get_document_content(doc1)
            content2 = DocumentComparisonService._get_document_content(doc2)

            # Vérifier si le document a un fichier original
            if doc1.file and os.path.exists(doc1.file.path):
                print(f"[INFO] Fichier original trouvé: {doc1.file.path}")

                # Récupérer la structure PDF stockée si disponible
                pdf_structure = None
                if hasattr(doc1, 'content') and doc1.content.pdf_structure:
                    pdf_structure = doc1.content.pdf_structure
                    print(f"[INFO] Structure PDF récupérée de la DB: {pdf_structure.get('total_tables', 0)} tableau(x)")
                else:
                    print(f"[WARNING] Pas de structure PDF stockée pour ce document")

                # Modifier le fichier en préservant sa structure
                print(f"[INFO] Appel de DocumentModifierService.apply_changes_to_file()...")
                success, message, modified_file_buffer = DocumentModifierService.apply_changes_to_file(
                    original_file_path=doc1.file.path,
                    doc1_content=content1,
                    doc2_content=content2,
                    doc1_title=doc1.title,
                    doc2_title=doc2.title,
                    pdf_structure_stored=pdf_structure
                )

                print(f"[INFO] Résultat de apply_changes_to_file: success={success}, message={message}, buffer={'présent' if modified_file_buffer else 'absent'}")

                if success and modified_file_buffer:
                    # Sauvegarder l'ancien nom de fichier
                    old_filename = os.path.basename(doc1.file.name)
                    file_ext = os.path.splitext(old_filename)[1]
                    new_filename = f"{doc1.title}_updated{file_ext}"

                    # Supprimer l'ancien fichier
                    old_file_path = doc1.file.path
                    doc1.file.delete(save=False)

                    # Sauvegarder le nouveau fichier
                    doc1.file.save(new_filename, ContentFile(modified_file_buffer.read()), save=False)

                    # Mettre à jour le contenu texte également
                    from documents.services import DocumentExtractorService
                    import os
                    file_ext = os.path.splitext(doc1.file.path)[1]
                    extraction_result = DocumentExtractorService.extract_text(doc1.file.path, file_ext)
                    extracted_content = extraction_result.get('text', '')

                    if hasattr(doc1, 'content'):
                        doc1.content.raw_text = extracted_content
                        doc1.content.word_count = len(extracted_content.split())
                        doc1.content.save()
                    else:
                        from documents.models import DocumentContent
                        DocumentContent.objects.create(
                            document=doc1,
                            raw_text=extracted_content,
                            word_count=len(extracted_content.split())
                        )

                    doc1.save()

                    processing_time = time.time() - start_time

                    return {
                        'success': True,
                        'message': 'Les changements ont été appliqués avec succès au document. La mise en forme originale a été préservée.',
                        'processing_time': processing_time,
                        'updated_word_count': len(extracted_content.split()),
                        'file_modified': True
                    }
                else:
                    # Échec de la modification du fichier, fallback sur mise à jour texte uniquement
                    print(f"[WARNING] Échec de la modification du fichier, fallback vers mise à jour texte uniquement")
                    print(f"[WARNING] Raison: success={success}, message={message}")
                    return DocumentUpdateService._apply_text_only_update(doc1, content1, content2, start_time)
            else:
                # Pas de fichier original, mise à jour texte uniquement
                print(f"[WARNING] Pas de fichier original (doc1.file={bool(doc1.file)}, exists={os.path.exists(doc1.file.path) if doc1.file else False})")
                return DocumentUpdateService._apply_text_only_update(doc1, content1, content2, start_time)

        except Exception as e:
            print(f"[ERROR] apply_changes_to_document: {e}")
            return {
                'success': False,
                'error': f'Erreur lors de l\'application des changements: {str(e)}'
            }

    @staticmethod
    def _apply_text_only_update(doc1: Document, content1: str, content2: str, start_time: float) -> Dict:
        """
        Fallback: Mise à jour du texte uniquement (sans modification du fichier)
        """
        try:
            # Utiliser le LLM pour générer la version propre sans marqueurs
            updated_content = DocumentUpdateService._generate_clean_update(
                doc1.title, content1,
                doc1.title, content2
            )

            # Mettre à jour le contenu du Document 1
            if hasattr(doc1, 'content'):
                doc1.content.raw_text = updated_content
                doc1.content.word_count = len(updated_content.split())
                doc1.content.save()
            else:
                # Créer le contenu s'il n'existe pas
                from documents.models import DocumentContent
                DocumentContent.objects.create(
                    document=doc1,
                    raw_text=updated_content,
                    word_count=len(updated_content.split())
                )

            processing_time = time.time() - start_time

            return {
                'success': True,
                'message': 'Les changements ont été appliqués au contenu texte (fichier original non modifié)',
                'processing_time': processing_time,
                'updated_word_count': len(updated_content.split()),
                'file_modified': False
            }

        except Exception as e:
            print(f"[ERROR] _apply_text_only_update: {e}")
            return {
                'success': False,
                'error': f'Erreur lors de la mise à jour du texte: {str(e)}'
            }

    @staticmethod
    def _generate_with_llm(title1: str, content1: str, title2: str, content2: str, changes: list = None) -> Dict:
        """
        Utilise le LLM pour générer un document mis à jour
        """
        if not GROQ_AVAILABLE or not hasattr(settings, 'GROQ_API_KEY') or not settings.GROQ_API_KEY:
            return {
                'content': content1,
                'type': 'original',
                'message': 'API non configurée - Document original retourné'
            }

        try:
            client = Groq(api_key=settings.GROQ_API_KEY)

            # Limiter la longueur
            max_length = 5000
            content1_truncated = content1[:max_length]
            content2_truncated = content2[:max_length]

            changes_instruction = ""
            if changes:
                changes_instruction = f"\n\nModifications spécifiques à appliquer:\n" + "\n".join(f"- {change}" for change in changes)

            prompt = f"""Tu es un expert en fusion de documents. Tu dois créer une version mise à jour du Document 1 en intégrant les améliorations pertinentes du Document 2.

DOCUMENT 1 (Version à mettre à jour): "{title1}"
{content1_truncated}

---

DOCUMENT 2 (Référence pour les améliorations): "{title2}"
{content2_truncated}

---

INSTRUCTIONS:
1. Prends le Document 1 comme base
2. Identifie les améliorations, ajouts et corrections pertinents du Document 2
3. Intègre ces améliorations dans le Document 1 de manière cohérente
4. Conserve la structure et le ton du Document 1
5. Améliore la clarté et la précision quand c'est pertinent
6. Marque les sections modifiées avec [MODIFIÉ] au début du paragraphe
7. Marque les nouveaux ajouts avec [AJOUTÉ] au début du paragraphe{changes_instruction}

Génère le document mis à jour complet en français, en conservant tout le formatage et la structure."""

            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant expert en édition et fusion de documents. Tu produis des documents clairs, cohérents et bien structurés en français."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=4000
            )

            updated_text = response.choices[0].message.content

            return {
                'content': updated_text,
                'type': 'llm_updated',
                'model': settings.GROQ_MODEL,
                'message': 'Document généré avec succès par IA'
            }

        except Exception as e:
            print(f"[ERROR] Erreur LLM génération: {e}")
            return {
                'content': content1,
                'type': 'error',
                'message': f'Erreur: {str(e)} - Document original retourné'
            }

    @staticmethod
    def _generate_clean_update(title1: str, content1: str, title2: str, content2: str) -> str:
        """
        Génère une version propre et mise à jour du document sans marqueurs
        Applique directement les changements sans annotations
        """
        if not GROQ_AVAILABLE or not hasattr(settings, 'GROQ_API_KEY') or not settings.GROQ_API_KEY:
            return content1

        try:
            client = Groq(api_key=settings.GROQ_API_KEY)

            # Limiter la longueur pour l'API
            max_length = 5000
            content1_truncated = content1[:max_length]
            content2_truncated = content2[:max_length]

            prompt = f"""Tu es un expert en fusion et mise à jour de documents. Tu dois créer une version propre et mise à jour du Document 1 en intégrant les améliorations du Document 2.

DOCUMENT 1 (Base à mettre à jour): "{title1}"
{content1_truncated}

---

DOCUMENT 2 (Source des améliorations): "{title2}"
{content2_truncated}

---

INSTRUCTIONS IMPORTANTES:
1. Prends le Document 1 comme base structurelle
2. Identifie les différences, améliorations et ajouts pertinents du Document 2
3. Intègre DIRECTEMENT ces changements dans le Document 1 de manière fluide et naturelle
4. Conserve la mise en forme originale du Document 1 (titres, paragraphes, listes, etc.)
5. NE METS AUCUN marqueur comme [MODIFIÉ], [AJOUTÉ] ou autres annotations
6. Remplace uniquement les parties concernées par les versions améliorées
7. Le résultat doit être un document propre, cohérent et naturel
8. Conserve le ton et le style du Document 1

Génère le document final mis à jour en français, sans aucun marqueur, comme si c'était une version naturellement améliorée du Document 1."""

            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant expert en édition de documents. Tu produis des documents propres, cohérents et naturels en français, sans annotations ni marqueurs."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=4000
            )

            updated_text = response.choices[0].message.content

            # Nettoyer tout marqueur qui aurait pu être ajouté par erreur
            clean_text = updated_text.replace('[MODIFIÉ]', '').replace('[AJOUTÉ]', '')
            clean_text = clean_text.replace('[MODIFIED]', '').replace('[ADDED]', '')

            return clean_text.strip()

        except Exception as e:
            print(f"[ERROR] Erreur LLM clean update: {e}")
            return content1

    @staticmethod
    def extract_changes_list(comparison_text: str) -> list:
        """
        Extrait une liste de modifications suggérées depuis le texte de comparaison
        """
        changes = []

        # Parser le texte pour extraire les différences
        lines = comparison_text.split('\n')
        current_change = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Détecter les sections de différences
            if 'Document 1:' in line or 'Document 2:' in line:
                if current_change:
                    changes.append(current_change)
                current_change = line
            elif current_change and line.startswith('-'):
                current_change += ' ' + line

        if current_change:
            changes.append(current_change)

        return changes[:10]  # Limiter à 10 changements principaux


class DocumentComparisonService:
    """
    Service pour comparer deux documents et identifier les différences
    """

    @staticmethod
    def compare_documents(doc1: Document, doc2: Document) -> Dict:
        """
        Compare deux documents et retourne les différences identifiées par le LLM
        """
        start_time = time.time()

        try:
            # 1. Extraire le contenu des deux documents
            content1 = DocumentComparisonService._get_document_content(doc1)
            content2 = DocumentComparisonService._get_document_content(doc2)

            if not content1 or not content2:
                return {
                    'success': False,
                    'error': 'Impossible d\'extraire le contenu d\'un ou des deux documents'
                }

            # 2. Utiliser le LLM pour comparer les documents
            comparison_result = DocumentComparisonService._compare_with_llm(
                doc1.title, content1,
                doc2.title, content2
            )

            processing_time = time.time() - start_time

            return {
                'success': True,
                'doc1': {
                    'id': doc1.id,
                    'title': doc1.title,
                    'word_count': len(content1.split())
                },
                'doc2': {
                    'id': doc2.id,
                    'title': doc2.title,
                    'word_count': len(content2.split())
                },
                'comparison': comparison_result,
                'processing_time': processing_time
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Erreur lors de la comparaison: {str(e)}'
            }

    @staticmethod
    def _get_document_content(document: Document) -> str:
        """
        Récupère le contenu textuel d'un document
        """
        try:
            # Essayer d'abord avec DocumentContent
            if hasattr(document, 'content'):
                return document.content.raw_text

            # Sinon, essayer avec les chunks
            chunks = document.chunks.all().order_by('chunk_index')
            if chunks.exists():
                return '\n\n'.join([chunk.content for chunk in chunks])

            return ""
        except Exception as e:
            print(f"[ERROR] Erreur extraction contenu: {e}")
            return ""

    @staticmethod
    def _compare_with_llm(title1: str, content1: str, title2: str, content2: str) -> Dict:
        """
        Utilise le LLM pour comparer deux documents
        """
        # Vérifier si Groq est disponible
        print(f"[DEBUG] GROQ_AVAILABLE: {GROQ_AVAILABLE}")
        print(f"[DEBUG] hasattr(settings, 'GROQ_API_KEY'): {hasattr(settings, 'GROQ_API_KEY')}")
        if hasattr(settings, 'GROQ_API_KEY'):
            api_key_preview = settings.GROQ_API_KEY[:20] + "..." if settings.GROQ_API_KEY else "VIDE"
            print(f"[DEBUG] settings.GROQ_API_KEY: {api_key_preview}")

        if not GROQ_AVAILABLE:
            print("[WARNING] Groq n'est pas disponible (module non importé)")
            return DocumentComparisonService._simple_comparison(content1, content2)

        if not hasattr(settings, 'GROQ_API_KEY'):
            print("[WARNING] settings.GROQ_API_KEY n'existe pas")
            return DocumentComparisonService._simple_comparison(content1, content2)

        if not settings.GROQ_API_KEY:
            print("[WARNING] settings.GROQ_API_KEY est vide")
            return DocumentComparisonService._simple_comparison(content1, content2)

        print("[INFO] Toutes les vérifications passées, appel du LLM...")

        try:
            print(f"[INFO] Initialisation du client Groq...")
            client = Groq(api_key=settings.GROQ_API_KEY)
            print(f"[INFO] Client Groq initialisé avec succès")

            # Limiter la longueur des contenus pour l'API
            max_length = 6000
            content1_truncated = content1[:max_length]
            content2_truncated = content2[:max_length]
            print(f"[INFO] Longueurs des contenus: Doc1={len(content1)} chars (tronqué à {len(content1_truncated)}), Doc2={len(content2)} chars (tronqué à {len(content2_truncated)})")

            prompt = f"""Tu es un expert en analyse comparative de documents. Compare ces deux documents et identifie les différences principales.

DOCUMENT 1: "{title1}"
{content1_truncated}

---

DOCUMENT 2: "{title2}"
{content2_truncated}

---

Analyse ces deux documents et fournis une comparaison structurée avec:

1. **Résumé Exécutif**: Un bref résumé des principales différences (2-3 phrases)

2. **Différences de Contenu**: Liste les sections, paragraphes ou informations qui sont différentes entre les deux documents. Pour chaque différence:
   - Indique le sujet/thème concerné
   - Explique ce qui est dit dans le Document 1
   - Explique ce qui est dit dans le Document 2
   - Note l'importance de la différence (Majeure/Mineure)

3. **Éléments Ajoutés**: Liste les informations présentes dans le Document 2 mais absentes du Document 1

4. **Éléments Supprimés**: Liste les informations présentes dans le Document 1 mais absentes du Document 2

5. **Similitudes**: Brièvement, quels sont les points communs entre les deux documents

6. **Conclusion**: Une synthèse globale de l'évolution entre les deux versions

Réponds en français, de manière structurée et claire."""

            print(f"[INFO] Envoi de la requête au LLM (modèle: {settings.GROQ_MODEL})...")
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant expert en analyse comparative de documents. Tu fournis des analyses détaillées et structurées en français."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.5,
                max_tokens=3000
            )

            analysis_text = response.choices[0].message.content
            print(f"[SUCCESS] Réponse LLM reçue: {len(analysis_text)} caractères, {response.usage.total_tokens} tokens utilisés")

            return {
                'analysis': analysis_text,
                'type': 'llm',
                'model': settings.GROQ_MODEL
            }

        except Exception as e:
            print(f"[ERROR] Erreur LLM comparaison: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            print("[INFO] Basculement vers la comparaison simple...")
            return DocumentComparisonService._simple_comparison(content1, content2)

    @staticmethod
    def _simple_comparison(content1: str, content2: str) -> Dict:
        """
        Comparaison simple basée sur des métriques textuelles
        """
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        common_words = words1.intersection(words2)
        unique_to_doc1 = words1 - words2
        unique_to_doc2 = words2 - words1

        similarity = len(common_words) / max(len(words1), len(words2)) * 100 if words1 or words2 else 0

        analysis = f"""**Analyse de Similarité Basique**

**Similarité globale**: {similarity:.1f}%

**Statistiques**:
- Mots communs: {len(common_words)}
- Mots uniques au Document 1: {len(unique_to_doc1)}
- Mots uniques au Document 2: {len(unique_to_doc2)}

**Note**: Cette analyse est basique. Pour une comparaison détaillée, veuillez configurer l'API Groq.
"""

        return {
            'analysis': analysis,
            'type': 'simple',
            'similarity_score': similarity
        }


class ChatService:
    """
    Service principal pour gérer les conversations
    """

    @classmethod
    def process_user_query(cls, conversation: Conversation, query: str) -> Message:
        """
        Traite une question de l'utilisateur et génère une réponse
        """
        start_time = time.time()

        # 1. Créer le message utilisateur
        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=query
        )

        # 2. Récupérer le contexte pertinent
        contexts = []

        print(f"[DEBUG ChatService] use_documents={conversation.use_documents}, nombre docs={conversation.documents.count()}")

        if conversation.use_documents and conversation.documents.exists():
            documents = list(conversation.documents.all())
            print(f"[DEBUG ChatService] Documents de la conversation: {[d.title for d in documents]}")

            doc_contexts = ContextRetrievalService.retrieve_from_documents(
                query,
                documents
            )
            print(f"[DEBUG ChatService] Contextes récupérés: {len(doc_contexts)}")
            contexts.extend(doc_contexts)
        else:
            print("[DEBUG ChatService] ATTENTION: Pas de documents associés à la conversation!")

        if conversation.use_external_db and conversation.external_db:
            db_contexts = ContextRetrievalService.retrieve_from_database(
                query,
                conversation.external_db
            )
            contexts.extend(db_contexts)

        # 3. Sauvegarder les contextes
        for ctx in contexts:
            QueryContext.objects.create(
                message=user_message,
                document=ctx.get('document'),
                content=ctx['content'],
                relevance_score=ctx['relevance_score'],
                page_number=ctx.get('page_number'),
                chunk_index=ctx.get('chunk_index')
            )

        # 4. Générer la réponse
        print(f"[DEBUG ChatService] Nombre total de contextes avant génération: {len(contexts)}")
        if contexts:
            print(f"[DEBUG ChatService] Premier contexte (extrait): {contexts[0]['content'][:200]}...")

        response_text = ResponseGeneratorService.generate_llm_response(
            query,
            contexts
        )

        # 5. Créer le message de réponse
        response_time = time.time() - start_time

        # Extraire les IDs des documents sources
        source_ids = []
        for ctx in contexts:
            doc = ctx.get('document')
            if doc and hasattr(doc, 'id'):
                source_ids.append(doc.id)

        assistant_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=response_text,
            response_time=response_time,
            sources_used=source_ids
        )

        # 6. Mettre à jour la conversation
        conversation.save()  # Met à jour updated_at

        return assistant_message

    @staticmethod
    def create_conversation(user, title: str, document_ids: List[int] = None, external_db_id: int = None) -> Conversation:
        """
        Crée une nouvelle conversation
        """
        conversation = Conversation.objects.create(
            user=user,
            title=title,
            use_documents=bool(document_ids),
            use_external_db=bool(external_db_id)
        )

        if document_ids:
            documents = Document.objects.filter(id__in=document_ids, user=user)
            conversation.documents.set(documents)

        if external_db_id:
            try:
                external_db = ExternalDatabase.objects.get(id=external_db_id, user=user)
                conversation.external_db = external_db
                conversation.save()
            except ExternalDatabase.DoesNotExist:
                pass

        return conversation

    @staticmethod
    def get_conversation_history(conversation: Conversation) -> List[Dict]:
        """
        Récupère l'historique d'une conversation
        """
        messages = conversation.messages.all().order_by('created_at')

        return [
            {
                'role': msg.role,
                'content': msg.content,
                'created_at': msg.created_at,
                'response_time': msg.response_time if msg.role == 'assistant' else None
            }
            for msg in messages
        ]
