# FICHIER: chat/pdf_extractor.py
# Service pour extraire la structure complète des PDF (texte + tableaux + positions)

from typing import Dict, List, Optional
from pathlib import Path

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


class PDFStructureExtractor:
    """
    Extracteur avancé pour PDF qui préserve la structure (tableaux, colonnes, etc.)
    """

    @staticmethod
    def extract_structure(pdf_path: str) -> Dict:
        """
        Extrait la structure complète d'un PDF incluant texte et tableaux

        Returns:
            {
                'success': bool,
                'pages': [
                    {
                        'page_number': int,
                        'text': str,
                        'tables': [
                            {
                                'data': [[cell, cell, ...], [row2...], ...],
                                'bbox': (x0, y0, x1, y1),
                            }
                        ],
                        'width': float,
                        'height': float
                    }
                ],
                'total_pages': int
            }
        """
        if not PDFPLUMBER_AVAILABLE:
            return {
                'success': False,
                'error': 'pdfplumber non installé',
                'pages': [],
                'total_pages': 0
            }

        try:
            pages_data = []

            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_info = {
                        'page_number': page_num,
                        'text': '',
                        'tables': [],
                        'width': page.width,
                        'height': page.height
                    }

                    # Extraire les tableaux avec paramètres plus permissifs
                    # Essayer d'abord avec la méthode standard
                    tables = page.extract_tables()

                    # Si pas de tableaux détectés, essayer avec des paramètres personnalisés
                    if not tables or len(tables) == 0:
                        # Paramètres plus permissifs pour détecter les tableaux "implicites"
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
                            if table and len(table) > 0:  # Vérifier que le tableau n'est pas vide
                                # Nettoyer les cellules None
                                cleaned_table = [
                                    [cell.strip() if cell is not None else '' for cell in row]
                                    for row in table
                                ]
                                # Filtrer les lignes complètement vides
                                cleaned_table = [row for row in cleaned_table if any(cell for cell in row)]

                                if cleaned_table:  # Seulement ajouter si le tableau nettoyé n'est pas vide
                                    page_info['tables'].append({
                                        'data': cleaned_table,
                                        'rows': len(cleaned_table),
                                        'cols': len(cleaned_table[0]) if cleaned_table else 0
                                    })

                    # Extraire le texte (en dehors des tableaux si possible)
                    full_text = page.extract_text()
                    if full_text:
                        page_info['text'] = full_text

                    pages_data.append(page_info)

            return {
                'success': True,
                'pages': pages_data,
                'total_pages': len(pages_data)
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'pages': [],
                'total_pages': 0
            }

    @staticmethod
    def extract_text_with_structure(pdf_path: str) -> str:
        """
        Extrait le texte en essayant de préserver la structure visuelle
        (tableaux convertis en texte formaté)
        """
        structure = PDFStructureExtractor.extract_structure(pdf_path)

        if not structure['success']:
            return ''

        full_text = []

        for page in structure['pages']:
            # Ajouter le texte de la page
            if page['text']:
                full_text.append(page['text'])

            # Convertir les tableaux en texte formaté
            for table_info in page['tables']:
                table_text = PDFStructureExtractor._format_table_as_text(table_info['data'])
                full_text.append(table_text)

            # Saut de page
            full_text.append('\n--- Page {} ---\n'.format(page['page_number']))

        return '\n\n'.join(full_text)

    @staticmethod
    def _format_table_as_text(table_data: List[List[str]]) -> str:
        """
        Convertit un tableau en texte formaté lisible
        """
        if not table_data:
            return ''

        # Calculer la largeur maximale de chaque colonne
        col_widths = []
        num_cols = len(table_data[0]) if table_data else 0

        for col_idx in range(num_cols):
            max_width = 0
            for row in table_data:
                if col_idx < len(row):
                    cell_value = str(row[col_idx]).strip()
                    max_width = max(max_width, len(cell_value))
            col_widths.append(max_width + 2)  # Padding

        # Construire le tableau formaté
        lines = []
        separator = '+' + '+'.join(['-' * width for width in col_widths]) + '+'

        lines.append(separator)

        for row in table_data:
            row_text = '|'
            for col_idx, cell in enumerate(row):
                cell_value = str(cell).strip()
                width = col_widths[col_idx]
                row_text += ' ' + cell_value.ljust(width - 1) + '|'
            lines.append(row_text)
            lines.append(separator)

        return '\n'.join(lines)

    @staticmethod
    def get_tables_count(pdf_path: str) -> int:
        """
        Retourne le nombre total de tableaux dans le PDF
        """
        structure = PDFStructureExtractor.extract_structure(pdf_path)
        if not structure['success']:
            return 0

        total_tables = 0
        for page in structure['pages']:
            total_tables += len(page['tables'])

        return total_tables

    @staticmethod
    def has_tables(pdf_path: str) -> bool:
        """
        Vérifie si le PDF contient des tableaux
        """
        return PDFStructureExtractor.get_tables_count(pdf_path) > 0
