# FICHIER: documents/services.py
# SERVICES POUR L'ANALYSE ET LE TRAITEMENT DES DOCUMENTS
# ============================================

import PyPDF2
import docx
import os
import json
from typing import Dict, List, Tuple
from django.core.files.uploadedfile import UploadedFile
from .models import Document, DocumentContent, DocumentAnalysis, DocumentChunk

# Import conditionnel de pdfplumber
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


class DocumentExtractorService:
    """
    Service pour extraire le contenu textuel des documents
    """

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> Tuple[str, int]:
        """
        Extrait le texte d'un fichier PDF
        Returns: (text, page_count)
        """
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                page_count = len(pdf_reader.pages)
                text = ""

                for page_num in range(page_count):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"

                return text, page_count
        except Exception as e:
            raise Exception(f"Erreur lors de l'extraction du PDF: {str(e)}")

    @staticmethod
    def extract_pdf_structure(file_path: str) -> Dict:
        """
        Extrait la structure complète du PDF avec pdfplumber (tableaux, texte, mise en page)
        Returns: Dict contenant la structure complète
        """
        if not PDFPLUMBER_AVAILABLE:
            print("[WARNING] pdfplumber non disponible, extraction simple utilisée")
            return None

        try:
            pages_data = []
            full_text = ""

            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_info = {
                        'page_number': page_num,
                        'text': '',
                        'tables': [],
                        'width': float(page.width),
                        'height': float(page.height)
                    }

                    # Extraire les tableaux avec paramètres permissifs
                    tables = page.extract_tables()

                    if not tables or len(tables) == 0:
                        # Essayer avec paramètres personnalisés
                        table_settings = {
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                            "snap_tolerance": 5,
                            "join_tolerance": 5,
                            "edge_min_length": 10,
                            "min_words_vertical": 2,
                            "min_words_horizontal": 2,
                        }
                        tables = page.extract_tables(table_settings=table_settings)

                    if tables:
                        for table in tables:
                            if table and len(table) > 0:
                                # Nettoyer les cellules
                                cleaned_table = [
                                    [str(cell).strip() if cell is not None else '' for cell in row]
                                    for row in table
                                ]
                                # Filtrer les lignes vides
                                cleaned_table = [row for row in cleaned_table if any(cell for cell in row)]

                                if cleaned_table:
                                    page_info['tables'].append({
                                        'data': cleaned_table,
                                        'rows': len(cleaned_table),
                                        'cols': len(cleaned_table[0]) if cleaned_table else 0
                                    })

                    # Extraire le texte
                    page_text = page.extract_text()
                    if page_text:
                        page_info['text'] = page_text
                        full_text += page_text + "\n\n"

                    pages_data.append(page_info)

            return {
                'success': True,
                'pages': pages_data,
                'total_pages': len(pages_data),
                'full_text': full_text,
                'has_tables': any(len(p.get('tables', [])) > 0 for p in pages_data),
                'total_tables': sum(len(p.get('tables', [])) for p in pages_data)
            }

        except Exception as e:
            print(f"[ERROR] extract_pdf_structure: {e}")
            return None

    @staticmethod
    def extract_text_from_docx(file_path: str) -> Tuple[str, int]:
        """
        Extrait le texte d'un fichier Word (.docx)
        Returns: (text, paragraph_count)
        """
        try:
            doc = docx.Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs]
            text = "\n".join(paragraphs)
            return text, len(paragraphs)
        except Exception as e:
            raise Exception(f"Erreur lors de l'extraction du DOCX: {str(e)}")

    @staticmethod
    def extract_text_from_txt(file_path: str) -> Tuple[str, int]:
        """
        Extrait le texte d'un fichier texte
        Returns: (text, line_count)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
                lines = text.split('\n')
                return text, len(lines)
        except Exception as e:
            raise Exception(f"Erreur lors de la lecture du fichier texte: {str(e)}")

    @classmethod
    def extract_text(cls, file_path: str, file_extension: str) -> Dict:
        """
        Extrait le texte selon le type de fichier
        Pour les PDF, extrait aussi la structure complète (tableaux, mise en page)
        Returns: Dict with 'text', 'page_count', 'word_count', 'pdf_structure'
        """
        text = ""
        page_count = 0
        pdf_structure = None

        if file_extension == '.pdf':
            # Essayer d'abord avec pdfplumber pour extraire la structure
            pdf_structure = cls.extract_pdf_structure(file_path)

            if pdf_structure and pdf_structure.get('success'):
                # Utiliser le texte extrait par pdfplumber (meilleure qualité)
                text = pdf_structure.get('full_text', '')
                page_count = pdf_structure.get('total_pages', 0)

                print(f"[INFO] PDF extrait avec pdfplumber: {page_count} pages, {pdf_structure.get('total_tables', 0)} tableau(x)")
            else:
                # Fallback sur PyPDF2 si pdfplumber échoue
                text, page_count = cls.extract_text_from_pdf(file_path)
                print(f"[INFO] PDF extrait avec PyPDF2 (fallback): {page_count} pages")

        elif file_extension in ['.docx', '.doc']:
            text, page_count = cls.extract_text_from_docx(file_path)
        elif file_extension == '.txt':
            text, page_count = cls.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Type de fichier non supporté: {file_extension}")

        # Calculer le nombre de mots
        word_count = len(text.split())

        result = {
            'text': text,
            'page_count': page_count,
            'word_count': word_count
        }

        # Ajouter la structure PDF si disponible
        if pdf_structure:
            result['pdf_structure'] = pdf_structure

        return result


class DocumentAnalyzerService:
    """
    Service pour analyser le contenu des documents avec NLP
    """

    @staticmethod
    def generate_summary(text: str, max_length: int = 500) -> str:
        """
        Génère un résumé du texte
        Note: Version simplifiée - à améliorer avec un vrai modèle NLP
        """
        # Version simple: prendre les premiers paragraphes
        sentences = text.split('.')
        summary = ""

        for sentence in sentences:
            if len(summary) + len(sentence) < max_length:
                summary += sentence + "."
            else:
                break

        return summary.strip()

    @staticmethod
    def extract_keywords(text: str, top_n: int = 10) -> List[str]:
        """
        Extrait les mots-clés principaux
        Note: Version simplifiée - à améliorer avec TF-IDF ou autre
        """
        # Liste de mots vides en français
        stop_words = {
            'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou',
            'dans', 'sur', 'pour', 'par', 'avec', 'sans', 'sous', 'ce', 'ces',
            'est', 'sont', 'a', 'ai', 'ont', 'que', 'qui', 'quoi', 'dont'
        }

        # Nettoyer et séparer les mots
        words = text.lower().split()
        words = [w.strip('.,!?;:()[]{}""\'') for w in words]

        # Filtrer les mots vides et courts
        words = [w for w in words if w not in stop_words and len(w) > 3]

        # Compter les occurrences
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1

        # Trier par fréquence
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

        return [word for word, freq in sorted_words[:top_n]]

    @staticmethod
    def extract_entities(text: str) -> Dict:
        """
        Extrait les entités nommées (personnes, lieux, organisations, dates)
        Note: Version simplifiée - à améliorer avec spaCy ou autre
        """
        # Version simplifiée - retourne une structure vide pour l'instant
        entities = {
            'persons': [],
            'organizations': [],
            'locations': [],
            'dates': []
        }

        # TODO: Implémenter avec spaCy ou un autre outil NLP

        return entities

    @staticmethod
    def detect_structure(text: str) -> Dict:
        """
        Détecte la structure du document (chapitres, sections, etc.)
        """
        structure = {
            'sections': [],
            'has_table_of_contents': False,
            'has_bibliography': False
        }

        lines = text.split('\n')

        # Détecter les titres (lignes courtes en majuscules ou avec numérotation)
        for i, line in enumerate(lines):
            line = line.strip()

            # Détection simple de sections
            if len(line) < 100 and len(line) > 0:
                # Vérifier si c'est un titre numéroté (1., I., A., etc.)
                if any(line.startswith(prefix) for prefix in ['1.', '2.', '3.', 'I.', 'II.', 'III.', 'A.', 'B.']):
                    structure['sections'].append({
                        'title': line,
                        'line_number': i
                    })

        return structure

    @staticmethod
    def detect_language(text: str) -> str:
        """
        Détecte la langue du document
        """
        # Mots-clés français
        french_words = {'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'est', 'dans', 'pour', 'avec', 'que'}
        # Mots-clés anglais
        english_words = {'the', 'a', 'an', 'of', 'and', 'is', 'in', 'for', 'with', 'that', 'this'}

        words = set(text.lower().split()[:200])  # Analyser les 200 premiers mots

        french_count = len(words.intersection(french_words))
        english_count = len(words.intersection(english_words))

        if french_count > english_count:
            return 'Français'
        elif english_count > french_count:
            return 'Anglais'
        else:
            return 'Non détectée'

    @staticmethod
    def detect_document_type(text: str, document_title: str = '') -> str:
        """
        Détecte le type de document
        """
        text_lower = text.lower()
        title_lower = document_title.lower()

        # Patterns pour différents types de documents
        if any(word in text_lower for word in ['contrat', 'contract', 'agreement', 'accord']):
            return 'Contrat'
        elif any(word in text_lower for word in ['rapport', 'report', 'étude', 'study']):
            return 'Rapport'
        elif any(word in text_lower for word in ['facture', 'invoice', 'devis', 'quote']):
            return 'Document financier'
        elif any(word in text_lower for word in ['guideline', 'directive', 'règlement', 'regulation']):
            return 'Directive/Règlement'
        elif any(word in text_lower for word in ['manuel', 'manual', 'guide', 'documentation']):
            return 'Manuel/Guide'
        elif any(word in text_lower for word in ['article', 'publication', 'journal', 'research']):
            return 'Article/Publication'
        elif any(word in text_lower for word in ['lettre', 'letter', 'correspondance']):
            return 'Lettre/Correspondance'
        else:
            return 'Document général'

    @classmethod
    def analyze_document(cls, document: Document, content_text: str) -> Dict:
        """
        Analyse complète d'un document
        """
        return {
            'summary': cls.generate_summary(content_text),
            'keywords': cls.extract_keywords(content_text),
            'entities': cls.extract_entities(content_text),
            'structure': cls.detect_structure(content_text),
            'detected_document_type': cls.detect_document_type(content_text, document.title),
            'language': cls.detect_language(content_text),
            'confidence_score': 75.0  # Score par défaut
        }


class DocumentChunkerService:
    """
    Service pour découper les documents en segments pour la recherche
    """

    @staticmethod
    def chunk_by_sentences(text: str, chunk_size: int = 500) -> List[str]:
        """
        Découpe le texte en chunks basés sur les phrases
        """
        sentences = text.split('.')
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    @staticmethod
    def chunk_by_paragraphs(text: str, max_chunk_size: int = 1000) -> List[str]:
        """
        Découpe le texte en chunks basés sur les paragraphes
        """
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if len(current_chunk) + len(para) < max_chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    @classmethod
    def create_chunks(cls, document: Document, text: str) -> List[DocumentChunk]:
        """
        Crée les chunks pour un document
        """
        chunks = cls.chunk_by_paragraphs(text)
        chunk_objects = []

        for i, chunk_content in enumerate(chunks):
            chunk = DocumentChunk(
                document=document,
                chunk_index=i,
                content=chunk_content
            )
            chunk_objects.append(chunk)

        return chunk_objects


class DocumentProcessorService:
    """
    Service principal pour orchestrer le traitement complet d'un document
    """

    @classmethod
    def process_document(cls, document: Document) -> bool:
        """
        Traite complètement un document:
        1. Extraction du texte
        2. Analyse NLP
        3. Création des chunks
        4. Mise à jour du statut
        """
        try:
            # Mettre le statut en "processing"
            document.status = 'processing'
            document.save()

            # 1. Extraire le texte
            file_path = document.file.path
            file_extension = document.get_file_extension()

            extraction_result = DocumentExtractorService.extract_text(
                file_path,
                file_extension
            )

            # 2. Créer ou mettre à jour le contenu
            defaults = {
                'raw_text': extraction_result['text'],
                'processed_text': extraction_result['text'],
                'word_count': extraction_result['word_count'],
                'page_count': extraction_result['page_count']
            }

            # Ajouter la structure PDF si disponible
            if 'pdf_structure' in extraction_result and extraction_result['pdf_structure']:
                defaults['pdf_structure'] = extraction_result['pdf_structure']
                print(f"[INFO] Structure PDF stockée: {extraction_result['pdf_structure'].get('total_tables', 0)} tableau(x)")

            content, created = DocumentContent.objects.get_or_create(
                document=document,
                defaults=defaults
            )

            if not created:
                content.raw_text = extraction_result['text']
                content.processed_text = extraction_result['text']
                content.word_count = extraction_result['word_count']
                content.page_count = extraction_result['page_count']

                # Mettre à jour la structure PDF si disponible
                if 'pdf_structure' in extraction_result and extraction_result['pdf_structure']:
                    content.pdf_structure = extraction_result['pdf_structure']
                    print(f"[INFO] Structure PDF mise à jour: {extraction_result['pdf_structure'].get('total_tables', 0)} tableau(x)")

                content.save()

            # 3. Analyser le document
            analysis_result = DocumentAnalyzerService.analyze_document(
                document,
                extraction_result['text']
            )

            # Créer ou mettre à jour l'analyse
            analysis, created = DocumentAnalysis.objects.get_or_create(
                document=document,
                defaults={
                    'summary': analysis_result['summary'],
                    'keywords': analysis_result['keywords'],
                    'entities': analysis_result['entities'],
                    'structure': analysis_result['structure'],
                    'detected_document_type': analysis_result.get('detected_document_type', 'Document général'),
                    'language': analysis_result.get('language', 'Non détectée'),
                    'confidence_score': analysis_result.get('confidence_score', 75.0)
                }
            )

            if not created:
                analysis.summary = analysis_result['summary']
                analysis.keywords = analysis_result['keywords']
                analysis.entities = analysis_result['entities']
                analysis.structure = analysis_result['structure']
                analysis.detected_document_type = analysis_result.get('detected_document_type', 'Document général')
                analysis.language = analysis_result.get('language', 'Non détectée')
                analysis.confidence_score = analysis_result.get('confidence_score', 75.0)
                analysis.save()

            # 4. Créer les chunks
            document.chunks.all().delete()  # Supprimer les anciens chunks
            chunks = DocumentChunkerService.create_chunks(
                document,
                extraction_result['text']
            )
            DocumentChunk.objects.bulk_create(chunks)

            # 5. Mettre le statut en "completed"
            from django.utils import timezone
            document.status = 'completed'
            document.analyzed_at = timezone.now()
            document.save()

            return True

        except Exception as e:
            document.status = 'error'
            document.save()
            raise Exception(f"Erreur lors du traitement du document: {str(e)}")
