"""
Service de génération de PDF pour les documents mis à jour
"""
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import re
from datetime import datetime


class PDFDocumentGenerator:
    """
    Générateur de PDF avec formatage préservé pour les documents mis à jour
    """

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Configure les styles personnalisés pour le PDF"""

        # Style pour le titre principal
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#11998e'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))

        # Style pour les titres de sections
        self.styles.add(ParagraphStyle(
            name='CustomHeading1',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#11998e'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ))

        # Style pour les sous-titres
        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2193b0'),
            spaceAfter=10,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        ))

        # Style pour le texte normal
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['BodyText'],
            fontSize=11,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
            leading=14,
            fontName='Helvetica'
        ))

        # Style pour les sections modifiées
        self.styles.add(ParagraphStyle(
            name='Modified',
            parent=self.styles['BodyText'],
            fontSize=11,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
            leading=14,
            backColor=colors.HexColor('#fff3cd'),
            borderColor=colors.HexColor('#ffc107'),
            borderWidth=1,
            borderPadding=5,
            fontName='Helvetica'
        ))

        # Style pour les sections ajoutées
        self.styles.add(ParagraphStyle(
            name='Added',
            parent=self.styles['BodyText'],
            fontSize=11,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
            leading=14,
            backColor=colors.HexColor('#d4edda'),
            borderColor=colors.HexColor('#28a745'),
            borderWidth=1,
            borderPadding=5,
            fontName='Helvetica'
        ))

        # Style pour les listes
        self.styles.add(ParagraphStyle(
            name='CustomBullet',
            parent=self.styles['BodyText'],
            fontSize=11,
            leftIndent=20,
            spaceAfter=6,
            fontName='Helvetica'
        ))

    def generate_pdf(self, content: str, title: str, metadata: dict = None) -> BytesIO:
        """
        Génère un PDF à partir du contenu textuel

        Args:
            content: Contenu du document
            title: Titre du document
            metadata: Métadonnées supplémentaires (auteur, date, etc.)

        Returns:
            BytesIO: Objet BytesIO contenant le PDF généré
        """
        buffer = BytesIO()

        # Créer le document PDF
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Construire le contenu
        story = []

        # Page de titre
        story.extend(self._create_title_page(title, metadata))

        # Contenu du document
        story.extend(self._parse_content(content))

        # Générer le PDF
        doc.build(story)

        buffer.seek(0)
        return buffer

    def _create_title_page(self, title: str, metadata: dict = None) -> list:
        """Crée la page de titre du document"""
        story = []

        # Titre principal
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph(title, self.styles['CustomTitle']))
        story.append(Spacer(1, 0.5*inch))

        # Métadonnées
        if metadata:
            meta_style = ParagraphStyle(
                name='MetaData',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.grey,
                alignment=TA_CENTER
            )

            if metadata.get('original_doc'):
                story.append(Paragraph(f"<b>Document original:</b> {metadata['original_doc']}", meta_style))
                story.append(Spacer(1, 0.1*inch))

            if metadata.get('reference_doc'):
                story.append(Paragraph(f"<b>Document de référence:</b> {metadata['reference_doc']}", meta_style))
                story.append(Spacer(1, 0.1*inch))

            if metadata.get('processing_time'):
                story.append(Paragraph(f"<b>Temps de traitement:</b> {metadata['processing_time']:.2f}s", meta_style))
                story.append(Spacer(1, 0.1*inch))

            # Date de génération
            generation_date = datetime.now().strftime("%d/%m/%Y %H:%M")
            story.append(Paragraph(f"<b>Généré le:</b> {generation_date}", meta_style))

        story.append(PageBreak())

        return story

    def _parse_content(self, content: str) -> list:
        """Parse le contenu et crée les éléments du PDF"""
        story = []
        lines = content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                story.append(Spacer(1, 0.1*inch))
                i += 1
                continue

            # Détecter les marqueurs spéciaux
            if '[MODIFIÉ]' in line:
                # Section modifiée
                clean_line = line.replace('[MODIFIÉ]', '').strip()
                badge = '<font color="#856404"><b>[MODIFIÉ]</b></font> '
                story.append(Paragraph(badge + clean_line, self.styles['Modified']))

            elif '[AJOUTÉ]' in line:
                # Section ajoutée
                clean_line = line.replace('[AJOUTÉ]', '').strip()
                badge = '<font color="#155724"><b>[AJOUTÉ]</b></font> '
                story.append(Paragraph(badge + clean_line, self.styles['Added']))

            # Détecter les titres (markdown-style)
            elif line.startswith('# '):
                # Titre niveau 1
                title_text = line[2:].strip()
                story.append(Paragraph(title_text, self.styles['CustomHeading1']))

            elif line.startswith('## '):
                # Titre niveau 2
                title_text = line[3:].strip()
                story.append(Paragraph(title_text, self.styles['CustomHeading2']))

            elif line.startswith('### '):
                # Titre niveau 3
                title_text = line[4:].strip()
                story.append(Paragraph(title_text, self.styles['Heading3']))

            # Détecter les listes
            elif line.startswith('- ') or line.startswith('* '):
                bullet_text = line[2:].strip()
                story.append(Paragraph(f'• {bullet_text}', self.styles['CustomBullet']))

            elif re.match(r'^\d+\.', line):
                # Liste numérotée
                story.append(Paragraph(line, self.styles['CustomBullet']))

            # Détecter le texte en gras
            elif '**' in line:
                # Convertir ** en balises HTML
                formatted_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                story.append(Paragraph(formatted_line, self.styles['CustomBody']))

            # Texte normal
            else:
                # Échapper les caractères spéciaux HTML
                safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(safe_line, self.styles['CustomBody']))

            i += 1

        return story

    def generate_comparison_summary_pdf(self, comparison_data: dict) -> BytesIO:
        """
        Génère un PDF récapitulatif de la comparaison
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []

        # Titre
        story.append(Paragraph("Rapport de Comparaison de Documents", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.3*inch))

        # Informations sur les documents
        doc1_title = comparison_data.get('doc1', {}).get('title', 'Document 1')
        doc2_title = comparison_data.get('doc2', {}).get('title', 'Document 2')

        data = [
            ['Document 1', doc1_title],
            ['Document 2', doc2_title],
            ['Mots (Doc 1)', str(comparison_data.get('doc1', {}).get('word_count', 'N/A'))],
            ['Mots (Doc 2)', str(comparison_data.get('doc2', {}).get('word_count', 'N/A'))],
        ]

        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#11998e')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        story.append(table)
        story.append(Spacer(1, 0.3*inch))

        # Analyse de comparaison
        analysis = comparison_data.get('comparison', {}).get('analysis', '')
        story.extend(self._parse_content(analysis))

        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_clean_document_pdf(self, title: str, content: str) -> BytesIO:
        """
        Génère un PDF propre du document mis à jour SANS marqueurs [MODIFIÉ] ou [AJOUTÉ]

        Args:
            title: Titre du document
            content: Contenu du document

        Returns:
            BytesIO: Objet BytesIO contenant le PDF généré
        """
        buffer = BytesIO()

        # Créer le document PDF
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Construire le contenu
        story = []

        # Titre du document
        story.append(Paragraph(title, self.styles['CustomTitle']))
        story.append(Spacer(1, 0.3*inch))

        # Informations de génération
        meta_style = ParagraphStyle(
            name='MetaData',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=20
        )

        generation_date = datetime.now().strftime("%d/%m/%Y à %H:%M")
        story.append(Paragraph(f"Document mis à jour - Généré le {generation_date}", meta_style))
        story.append(Spacer(1, 0.2*inch))

        # Contenu du document - Parser proprement sans marqueurs
        story.extend(self._parse_clean_content(content))

        # Générer le PDF
        doc.build(story)

        buffer.seek(0)
        return buffer

    def generate_pdf_from_structure(self, title: str, pdf_structure: dict, modifications: dict = None) -> BytesIO:
        """
        Génère un PDF à partir de la structure extraite (avec tableaux)

        Args:
            title: Titre du document
            pdf_structure: Structure extraite par PDFStructureExtractor
            modifications: Dict de modifications à appliquer {old_text: new_text}

        Returns:
            BytesIO contenant le PDF généré
        """
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        story = []

        # Titre
        story.append(Paragraph(title, self.styles['CustomTitle']))
        story.append(Spacer(1, 0.3*inch))

        # Parcourir toutes les pages
        for page_num, page in enumerate(pdf_structure.get('pages', []), 1):
            # Ajouter un saut de page avant chaque page (sauf la première)
            if page_num > 1:
                story.append(PageBreak())

            # Vérifier si la page contient des tableaux
            has_tables = len(page.get('tables', [])) > 0

            # Extraire le texte HORS tableaux (en-têtes, titres, notes)
            # Pour l'instant, on affiche tout le texte + les tableaux
            # TODO: Améliorer pour filtrer le contenu des tableaux du texte
            if page.get('text'):
                page_text = page['text']

                # Appliquer les modifications si fournies
                if modifications:
                    for old_text, new_text in modifications.items():
                        if old_text in page_text:
                            page_text = page_text.replace(old_text, new_text)

                # Pour les pages AVEC tableaux, afficher seulement les 2 premières lignes (en-tête)
                if has_tables:
                    lines = page_text.split('\n')
                    header_text = '\n'.join(lines[:2])  # Seulement les 2 premières lignes
                    if header_text.strip():
                        story.append(Paragraph(header_text, self.styles['Normal']))
                        story.append(Spacer(1, 0.1*inch))
                else:
                    # Pas de tableaux : afficher tout le texte
                    story.extend(self._parse_clean_content(page_text))

            # Tableaux de la page
            for table_info in page.get('tables', []):
                table_data = table_info['data']

                # Appliquer les modifications aux cellules si fournies
                if modifications:
                    table_data = self._apply_modifications_to_table(table_data, modifications)

                # Créer le tableau ReportLab
                if table_data:
                    # Calculer les largeurs de colonnes de manière intelligente
                    num_cols = len(table_data[0]) if table_data else 0
                    available_width = 7.0 * inch

                    # Calculer la largeur optimale basée sur le contenu
                    col_widths = []
                    if num_cols > 0:
                        max_lengths = [0] * num_cols
                        for row in table_data:
                            for col_idx, cell in enumerate(row[:num_cols]):  # Sécurité
                                cell_text = str(cell) if cell else ""
                                max_lengths[col_idx] = max(max_lengths[col_idx], len(cell_text))

                        # Convertir en largeurs proportionnelles avec largeur minimale
                        total_length = sum(max_lengths) or 1
                        for length in max_lengths:
                            proportion = max(length / total_length, 0.1)  # Min 10%
                            col_widths.append(available_width * proportion)
                    else:
                        col_widths = [available_width / num_cols] * num_cols

                    table = Table(table_data, colWidths=col_widths)

                    # Style du tableau - MINIMALISTE pour préserver l'aspect original
                    table.setStyle(TableStyle([
                        # Police simple et uniforme (taille réduite pour éviter le chevauchement)
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 7),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),

                        # Couleurs SIMPLES (noir sur blanc uniquement)
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('BACKGROUND', (0, 0), (-1, -1), colors.white),

                        # Bordures simples noires
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                        ('BOX', (0, 0), (-1, -1), 1, colors.black),

                        # Padding minimal
                        ('LEFTPADDING', (0, 0), (-1, -1), 3),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),

                        # Word wrap pour éviter le chevauchement
                        ('WORDWRAP', (0, 0), (-1, -1), True),
                    ]))

                    story.append(Spacer(1, 0.2*inch))
                    story.append(table)
                    story.append(Spacer(1, 0.2*inch))

        # Générer le PDF
        doc.build(story)
        buffer.seek(0)
        return buffer

    def _apply_modifications_to_table(self, table_data: list, modifications: dict) -> list:
        """
        Applique les modifications aux cellules d'un tableau
        """
        modified_table = []

        for row in table_data:
            modified_row = []
            for cell in row:
                cell_text = str(cell) if cell else ''

                # Appliquer les modifications
                for old_text, new_text in modifications.items():
                    if old_text in cell_text:
                        cell_text = cell_text.replace(old_text, new_text)

                modified_row.append(cell_text)
            modified_table.append(modified_row)

        return modified_table

    def _parse_clean_content(self, content: str) -> list:
        """
        Parse le contenu sans les marqueurs [MODIFIÉ] et [AJOUTÉ]
        Génère un document propre et naturel
        Détecte les structures tabulaires implicites
        """
        story = []
        lines = content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                story.append(Spacer(1, 0.1*inch))
                i += 1
                continue

            # Nettoyer les marqueurs si présents
            clean_line = line.replace('[MODIFIÉ]', '').replace('[AJOUTÉ]', '').strip()

            if not clean_line:
                i += 1
                continue

            # Détecter si c'est une ligne de tableau implicite (avec beaucoup d'espaces)
            if self._looks_like_table_row(clean_line):
                # Essayer de construire un mini-tableau
                table_lines = []
                j = i
                while j < len(lines) and self._looks_like_table_row(lines[j].strip()):
                    table_lines.append(lines[j].strip())
                    j += 1

                if len(table_lines) >= 2:  # Au moins 2 lignes pour faire un tableau
                    # Créer un tableau à partir de ces lignes
                    table_data = []
                    for tline in table_lines:
                        # Séparer par plusieurs espaces (au moins 2)
                        cells = re.split(r'\s{2,}', tline.strip())
                        cells = [cell.strip() for cell in cells if cell.strip()]
                        if cells:
                            table_data.append(cells)

                    if table_data and len(table_data) > 0:
                        # S'assurer que toutes les lignes ont le même nombre de colonnes
                        max_cols = max(len(row) for row in table_data)
                        normalized_data = []
                        for row in table_data:
                            while len(row) < max_cols:
                                row.append('')
                            normalized_data.append(row[:max_cols])

                        # Créer le tableau ReportLab
                        if normalized_data:
                            available_width = 6.5 * inch
                            col_width = available_width / max_cols

                            table = Table(normalized_data, colWidths=[col_width] * max_cols)
                            table.setStyle(TableStyle([
                                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2193b0')),
                                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                ('FONTSIZE', (0, 0), (-1, 0), 9),
                                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                                ('FONTSIZE', (0, 1), (-1, -1), 8),
                                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#2193b0')),
                                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                                ('TOPPADDING', (0, 0), (-1, -1), 4),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                            ]))
                            story.append(Spacer(1, 0.1*inch))
                            story.append(table)
                            story.append(Spacer(1, 0.1*inch))

                    i = j
                    continue

            # Détecter les titres (markdown-style)
            if clean_line.startswith('# '):
                title_text = clean_line[2:].strip()
                story.append(Paragraph(title_text, self.styles['CustomHeading1']))

            elif clean_line.startswith('## '):
                title_text = clean_line[3:].strip()
                story.append(Paragraph(title_text, self.styles['CustomHeading2']))

            elif clean_line.startswith('### '):
                title_text = clean_line[4:].strip()
                story.append(Paragraph(title_text, self.styles['Heading3']))

            # Détecter les listes
            elif clean_line.startswith('- ') or clean_line.startswith('* ') or clean_line.startswith('.'):
                bullet_text = clean_line[2:].strip() if clean_line[0] in ['-', '*', '.'] else clean_line
                story.append(Paragraph(f'• {bullet_text}', self.styles['CustomBullet']))

            elif re.match(r'^\d+\.', clean_line):
                story.append(Paragraph(clean_line, self.styles['CustomBullet']))

            # Détecter le texte en gras
            elif '**' in clean_line:
                formatted_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', clean_line)
                story.append(Paragraph(formatted_line, self.styles['CustomBody']))

            # Texte normal
            else:
                safe_line = clean_line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                # Utiliser une police monospace pour préserver l'alignement du texte
                if len(clean_line) > 80 or '\t' in line:  # Ligne longue ou avec tabs
                    preformat_style = ParagraphStyle(
                        name='Preformat',
                        parent=self.styles['Normal'],
                        fontSize=8,
                        fontName='Courier',
                        leftIndent=10,
                        spaceAfter=2,
                    )
                    story.append(Paragraph(safe_line, preformat_style))
                else:
                    story.append(Paragraph(safe_line, self.styles['CustomBody']))

            i += 1

        return story

    def _looks_like_table_row(self, line: str) -> bool:
        """
        Détecte si une ligne ressemble à une ligne de tableau
        (contient plusieurs sections séparées par des espaces multiples)
        """
        if not line or len(line) < 10:
            return False

        # Compter les séquences d'espaces multiples (au moins 2 espaces consécutifs)
        space_sequences = len(re.findall(r'\s{2,}', line))

        # Si au moins 2 séquences d'espaces, c'est probablement un tableau
        return space_sequences >= 2

    def generate_simple_pdf(self, title: str, content: str):
        """
        Génère un PDF simple avec un titre et du contenu
        Pour l'agent intelligent

        Args:
            title: Titre du document
            content: Contenu du document

        Returns:
            BytesIO buffer contenant le PDF
        """
        buffer = BytesIO()

        # Créer le document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=0.75*inch
        )

        story = []

        # Titre
        title_style = ParagraphStyle(
            'AgentTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.black,
            spaceAfter=0.3*inch,
            alignment=TA_CENTER
        )
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.2*inch))

        # Contenu (parser les lignes)
        for line in content.split('\n'):
            line = line.strip()
            if line:
                if line.startswith('#'):
                    # Titre
                    story.append(Paragraph(line.replace('#', '').strip(), self.styles['Heading2']))
                elif line.startswith('-'):
                    # Liste
                    story.append(Paragraph(f"• {line[1:].strip()}", self.styles['Normal']))
                elif line == '---':
                    # Séparateur
                    story.append(Spacer(1, 0.2*inch))
                else:
                    # Texte normal
                    safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_line, self.styles['Normal']))
            else:
                # Ligne vide = espace
                story.append(Spacer(1, 0.1*inch))

        # Construire le PDF
        doc.build(story)

        buffer.seek(0)
        return buffer
