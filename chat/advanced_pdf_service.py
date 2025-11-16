import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional
import base64
import io
import logging
from PIL import Image

# Configuration du logging
logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Exception personnalisée pour les erreurs d'extraction PDF"""
    pass


class AdvancedPDFExtractor:
    """
    Extracteur PDF avancé avec support du formatage fidèle.
    Extrait le texte, les images, les tableaux et préserve le formatage original.
    VERSION AMÉLIORÉE avec logging et gestion d'erreurs robuste.
    """

    def __init__(self, pdf_path: str):
        """
        Initialise l'extracteur PDF avec gestion d'erreurs.

        Args:
            pdf_path: Chemin vers le fichier PDF

        Raises:
            PDFExtractionError: Si le fichier n'existe pas ou n'est pas valide
        """
        self.pdf_path = pdf_path

        # Statistiques d'extraction
        self.stats = {
            'pages_extracted': 0,
            'text_blocks': 0,
            'images_extracted': 0,
            'tables_detected': 0,
            'errors': [],
            'warnings': []
        }

        # Vérification et ouverture du document
        try:
            import os
            if not os.path.exists(pdf_path):
                raise PDFExtractionError(f"Fichier PDF introuvable: {pdf_path}")

            self.doc = fitz.open(pdf_path)
            logger.info(f"PDF ouvert avec succès: {pdf_path} ({len(self.doc)} pages)")

        except fitz.fitz.FileNotFoundError as e:
            logger.error(f"Fichier PDF introuvable: {pdf_path}")
            raise PDFExtractionError(f"Fichier PDF introuvable: {pdf_path}") from e
        except fitz.fitz.FileDataError as e:
            logger.error(f"Fichier PDF corrompu ou invalide: {pdf_path}")
            raise PDFExtractionError(f"Fichier PDF corrompu: {pdf_path}") from e
        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture du PDF: {e}")
            raise PDFExtractionError(f"Impossible d'ouvrir le PDF: {e}") from e

    def __enter__(self):
        """Support du context manager"""
        logger.debug("Entrée dans le context manager PDF")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Fermeture automatique du document"""
        try:
            if self.doc:
                self.doc.close()
                logger.debug("Document PDF fermé")
        except Exception as e:
            logger.warning(f"Erreur lors de la fermeture du PDF: {e}")
        return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques d'extraction.

        Returns:
            Dict contenant les statistiques
        """
        return {
            **self.stats,
            'pdf_path': self.pdf_path,
            'total_pages': len(self.doc) if self.doc else 0
        }

    def extract_full_document(self) -> Dict[str, Any]:
        """
        Extrait le contenu complet du document PDF avec tout le formatage.
        Organise les éléments dans l'ordre de lecture (top-to-bottom).

        Returns:
            Dict contenant les pages avec texte formaté, images et tableaux organisés

        Raises:
            PDFExtractionError: Si l'extraction échoue complètement
        """
        import time
        start_time = time.time()

        pages_data = []
        logger.info(f"Début de l'extraction complète du PDF ({len(self.doc)} pages)")

        try:
            for page_num in range(len(self.doc)):
                page_start = time.time()
                try:
                    page = self.doc[page_num]
                    logger.debug(f"Traitement de la page {page_num + 1}/{len(self.doc)}")

                    # Extraire le texte avec formatage
                    text_blocks = []
                    try:
                        text_blocks = self._extract_formatted_text(page)
                        self.stats['text_blocks'] += len(text_blocks)
                        logger.debug(f"Page {page_num + 1}: {len(text_blocks)} blocs de texte extraits")
                    except Exception as e:
                        logger.warning(f"Erreur lors de l'extraction du texte de la page {page_num + 1}: {e}")
                        self.stats['warnings'].append(f"Page {page_num + 1}: Échec extraction texte")

                    # Extraire les images
                    images = []
                    try:
                        images = self._extract_images(page, page_num)
                        self.stats['images_extracted'] += len(images)
                        logger.debug(f"Page {page_num + 1}: {len(images)} images extraites")
                    except Exception as e:
                        logger.warning(f"Erreur lors de l'extraction des images de la page {page_num + 1}: {e}")
                        self.stats['warnings'].append(f"Page {page_num + 1}: Échec extraction images")

                    # Extraire les tableaux
                    tables = []
                    try:
                        tables = self._extract_tables(page)
                        self.stats['tables_detected'] += len(tables)
                        logger.debug(f"Page {page_num + 1}: {len(tables)} tableaux détectés")
                    except Exception as e:
                        logger.warning(f"Erreur lors de l'extraction des tableaux de la page {page_num + 1}: {e}")
                        self.stats['warnings'].append(f"Page {page_num + 1}: Échec extraction tableaux")

                    # Organiser tous les éléments dans l'ordre de lecture (top-to-bottom)
                    all_elements = []

                    # Ajouter les blocs de texte avec leur position
                    for block in text_blocks:
                        try:
                            bbox = block.get('bbox', [0, 0, 0, 0])
                            all_elements.append({
                                'type': 'text',
                                'data': block,
                                'y': bbox[1] if bbox and len(bbox) > 1 else 0,
                                'bbox': bbox
                            })
                        except Exception:
                            continue

                    # Ajouter les images
                    for img in images:
                        try:
                            bbox = img.get('bbox', [0, 0, 0, 0])
                            y = bbox[1] if isinstance(bbox, (list, tuple)) and len(bbox) > 1 else 0
                            all_elements.append({
                                'type': 'image',
                                'data': img,
                                'y': y,
                                'bbox': bbox
                            })
                        except Exception:
                            continue

                    # Ajouter les tableaux
                    for table in tables:
                        try:
                            bbox = table.get('bbox', [0, 0, 0, 0])
                            all_elements.append({
                                'type': 'table',
                                'data': table,
                                'y': bbox[1] if bbox and len(bbox) > 1 else 0,
                                'bbox': bbox
                            })
                        except Exception:
                            continue

                    # Trier tous les éléments par position Y (ordre de lecture)
                    try:
                        all_elements.sort(key=lambda el: el.get('y', 0))
                    except Exception as e:
                        logger.warning(f"Erreur lors du tri des éléments: {e}")

                    # Filtrer les blocs de texte qui se trouvent à l'intérieur des tableaux
                    filtered_elements = []
                    for element in all_elements:
                        try:
                            if element['type'] == 'text':
                                # Vérifier si ce bloc de texte est dans un tableau
                                is_in_table = False
                                for other in all_elements:
                                    try:
                                        if other['type'] == 'table':
                                            if self._is_inside(element['bbox'], other['bbox']):
                                                is_in_table = True
                                                break
                                    except Exception:
                                        continue

                                if not is_in_table:
                                    filtered_elements.append(element)
                            else:
                                filtered_elements.append(element)
                        except Exception:
                            continue

                    # Obtenir les dimensions de la page
                    page_width = 595  # A4 par défaut
                    page_height = 842
                    try:
                        page_width = page.rect.width
                        page_height = page.rect.height
                    except Exception:
                        pass

                    pages_data.append({
                        'page_number': page_num + 1,
                        'text_blocks': text_blocks,
                        'images': images,
                        'tables': tables,
                        'elements': filtered_elements,  # Éléments triés dans l'ordre
                        'width': page_width,
                        'height': page_height
                    })

                    self.stats['pages_extracted'] += 1
                    page_time = time.time() - page_start
                    logger.debug(f"Page {page_num + 1} traitée en {page_time:.2f}s")

                except Exception as e:
                    logger.error(f"Erreur lors de l'extraction de la page {page_num + 1}: {e}", exc_info=True)
                    self.stats['errors'].append(f"Page {page_num + 1}: {str(e)}")

                    # Ajouter une page vide en cas d'erreur
                    pages_data.append({
                        'page_number': page_num + 1,
                        'text_blocks': [],
                        'images': [],
                        'tables': [],
                        'elements': [],
                        'width': 595,
                        'height': 842,
                        'error': str(e)
                    })

            # Obtenir les métadonnées du document
            metadata = {}
            try:
                metadata = self.doc.metadata if self.doc.metadata else {}
                logger.debug(f"Métadonnées extraites: {list(metadata.keys())}")
            except Exception as e:
                logger.warning(f"Impossible d'extraire les métadonnées: {e}")
                self.stats['warnings'].append("Métadonnées non disponibles")

            # Calculer le temps total
            total_time = time.time() - start_time
            logger.info(
                f"Extraction terminée en {total_time:.2f}s - "
                f"{self.stats['pages_extracted']}/{len(self.doc)} pages, "
                f"{self.stats['text_blocks']} blocs texte, "
                f"{self.stats['images_extracted']} images, "
                f"{self.stats['tables_detected']} tableaux"
            )

            if self.stats['errors']:
                logger.warning(f"{len(self.stats['errors'])} erreurs rencontrées pendant l'extraction")

            return {
                'pages': pages_data,
                'total_pages': len(self.doc),
                'metadata': metadata,
                'stats': self.stats,
                'extraction_time': total_time
            }

        except Exception as e:
            logger.error(f"Erreur critique lors de l'extraction du document: {e}", exc_info=True)
            self.stats['errors'].append(f"Erreur critique: {str(e)}")

            # Retourner une structure minimale en cas d'erreur critique
            raise PDFExtractionError(f"Échec de l'extraction du PDF: {e}") from e

    def _is_inside(self, inner_bbox, outer_bbox) -> bool:
        """
        Vérifie si inner_bbox est à l'intérieur de outer_bbox.
        """
        return (inner_bbox[0] >= outer_bbox[0] - 5 and
                inner_bbox[1] >= outer_bbox[1] - 5 and
                inner_bbox[2] <= outer_bbox[2] + 5 and
                inner_bbox[3] <= outer_bbox[3] + 5)

    def _extract_formatted_text(self, page) -> List[Dict[str, Any]]:
        """
        Extrait le texte avec toutes les informations de formatage.
        Préserve le style, la taille, la couleur, etc.
        """
        text_blocks = []
        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Type 0 = texte
                continue

            block_data = {
                'bbox': block.get('bbox', [0, 0, 0, 0]),
                'lines': []
            }

            for line in block.get("lines", []):
                line_data = {
                    'bbox': line.get('bbox', [0, 0, 0, 0]),
                    'wmode': line.get('wmode', 0),
                    'dir': line.get('dir', [1, 0]),
                    'spans': []
                }

                for span in line.get("spans", []):
                    # Extraction des informations de style
                    font = span.get('font', '')
                    flags = span.get('flags', 0)

                    # Déterminer si le texte est en gras ou italique
                    is_bold = ('Bold' in font) or (flags & 2 ** 4)
                    is_italic = ('Italic' in font or 'Oblique' in font) or (flags & 2 ** 1)

                    # Extraire la couleur (RGB)
                    color_int = span.get('color', 0)
                    color = self._int_to_rgb_hex(color_int)

                    span_data = {
                        'text': span.get('text', ''),
                        'size': span.get('size', 12),
                        'font': font,
                        'bold': is_bold,
                        'italic': is_italic,
                        'color': color,
                        'bbox': span.get('bbox', [0, 0, 0, 0])
                    }

                    line_data['spans'].append(span_data)

                if line_data['spans']:  # Ajouter seulement si la ligne contient du texte
                    block_data['lines'].append(line_data)

            if block_data['lines']:  # Ajouter seulement si le bloc contient des lignes
                text_blocks.append(block_data)

        return text_blocks

    def _extract_images(self, page, page_num: int) -> List[Dict[str, Any]]:
        """
        Extrait toutes les images de la page avec leurs métadonnées.

        Returns:
            Liste des images avec leurs données en base64
        """
        images = []

        try:
            image_list = page.get_images(full=True)

            for img_index, img_info in enumerate(image_list):
                try:
                    if not img_info or len(img_info) == 0:
                        continue

                    xref = img_info[0]
                    base_image = self.doc.extract_image(xref)

                    if not base_image:
                        continue

                    image_bytes = base_image.get("image")
                    image_ext = base_image.get("ext", "png")

                    if not image_bytes:
                        continue

                    # Convertir en base64 pour l'éditeur
                    try:
                        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        image_data_uri = f"data:image/{image_ext};base64,{image_base64}"
                    except Exception as e:
                        logger.warning(f"Erreur lors de l'encodage base64 de l'image {img_index}: {e}")
                        continue

                    # Obtenir les dimensions de l'image
                    width, height = 100, 100  # Valeurs par défaut
                    try:
                        pil_image = Image.open(io.BytesIO(image_bytes))
                        width, height = pil_image.size
                    except Exception as e:
                        logger.debug(f"Impossible d'obtenir les dimensions de l'image {img_index}: {e}")

                    # Obtenir la position de l'image sur la page
                    bbox = [0, 0, width, height]  # Défaut
                    try:
                        img_rects = page.get_image_rects(xref)
                        if img_rects and len(img_rects) > 0:
                            bbox = list(img_rects[0])
                    except Exception as e:
                        logger.debug(f"Impossible d'obtenir la position de l'image {img_index}: {e}")

                    images.append({
                        'data': image_data_uri,
                        'width': width,
                        'height': height,
                        'bbox': bbox,
                        'ext': image_ext,
                        'xref': xref,
                        'page': page_num + 1
                    })
                except Exception as e:
                    logger.warning(f"Erreur lors de l'extraction de l'image {img_index}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des images de la page: {e}")

        return images

    def _extract_tables(self, page) -> List[Dict[str, Any]]:
        """
        Extraction avancée des tableaux en détectant les lignes et la structure.
        Utilise à la fois les lignes graphiques et l'alignement du texte.
        """
        tables = []

        try:
            # Méthode 1: Détecter les tableaux via les lignes graphiques (rectangles, lignes)
            horizontal_lines = []
            vertical_lines = []

            try:
                drawings = page.get_drawings()

                for drawing in drawings:
                    try:
                        # Analyser les chemins pour trouver les lignes
                        items = drawing.get("items", [])
                        for item in items:
                            try:
                                if len(item) < 2:
                                    continue

                                item_type = item[0]

                                if item_type == "l" and len(item) >= 5:  # ligne
                                    x0, y0, x1, y1 = item[1], item[2], item[3], item[4]
                                    if abs(y0 - y1) < 2:  # Ligne horizontale
                                        horizontal_lines.append((min(x0, x1), y0, max(x0, x1), y1))
                                    elif abs(x0 - x1) < 2:  # Ligne verticale
                                        vertical_lines.append((x0, min(y0, y1), x1, max(y0, y1)))
                                elif item_type == "re" and len(item) >= 5:  # rectangle
                                    x, y, w, h = item[1], item[2], item[3], item[4]
                                    # Ajouter les bords du rectangle comme lignes
                                    horizontal_lines.append((x, y, x + w, y))
                                    horizontal_lines.append((x, y + h, x + w, y + h))
                                    vertical_lines.append((x, y, x, y + h))
                                    vertical_lines.append((x + w, y, x + w, y + h))
                            except (IndexError, TypeError, ValueError) as e:
                                # Ignorer les items malformés
                                continue
                    except Exception as e:
                        # Ignorer les drawings problématiques
                        continue

                # Grouper les lignes proches pour former des grilles de tableaux
                if horizontal_lines and vertical_lines:
                    tables_from_lines = self._detect_tables_from_lines(
                        page, horizontal_lines, vertical_lines
                    )
                    if tables_from_lines:
                        tables.extend(tables_from_lines)
            except Exception as e:
                # Si la détection par lignes échoue, continuer avec la détection par texte
                logger.debug(f"Détection de tableaux par lignes échouée: {e}")

            # Méthode 2: Détecter les tableaux via l'alignement du texte en colonnes
            try:
                tables_from_text = self._detect_tables_from_text_alignment(page)

                # Fusionner les tableaux détectés en évitant les doublons
                for text_table in tables_from_text:
                    try:
                        # Vérifier si ce tableau n'est pas déjà détecté
                        is_duplicate = False
                        text_bbox = text_table.get('bbox', [0, 0, 0, 0])

                        for existing_table in tables:
                            existing_bbox = existing_table.get('bbox', [0, 0, 0, 0])
                            # Calculer le chevauchement
                            if self._boxes_overlap(text_bbox, existing_bbox, threshold=0.5):
                                is_duplicate = True
                                break

                        if not is_duplicate:
                            tables.append(text_table)
                    except Exception as e:
                        # Ignorer ce tableau s'il y a une erreur
                        continue
            except Exception as e:
                # Si la détection par texte échoue, retourner ce qu'on a
                logger.debug(f"Détection de tableaux par alignement échouée: {e}")

        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des tableaux: {e}")
            # Retourner une liste vide en cas d'erreur majeure

        return tables

    def _detect_tables_from_lines(self, page, h_lines, v_lines) -> List[Dict[str, Any]]:
        """
        Détecte les tableaux à partir des lignes graphiques.
        """
        tables = []

        try:
            if not h_lines or not v_lines:
                return tables

            # Trier les lignes avec gestion d'erreurs
            try:
                h_lines = sorted(set(h_lines), key=lambda l: (l[1], l[0]))
                v_lines = sorted(set(v_lines), key=lambda l: (l[0], l[1]))
            except (TypeError, IndexError) as e:
                logger.warning(f"Erreur lors du tri des lignes: {e}")
                return tables

            if not h_lines or not v_lines:
                return tables

            # Grouper les lignes horizontales proches (même Y)
            h_groups = []
            current_group = [h_lines[0]]

            for line in h_lines[1:]:
                try:
                    if abs(line[1] - current_group[-1][1]) < 5:  # Même hauteur (tolérance 5 points)
                        current_group.append(line)
                    else:
                        if current_group:
                            h_groups.append(current_group)
                        current_group = [line]
                except (IndexError, TypeError):
                    continue

            if current_group:
                h_groups.append(current_group)

            # Grouper les lignes verticales proches (même X)
            v_groups = []
            current_group = [v_lines[0]]

            for line in v_lines[1:]:
                try:
                    if abs(line[0] - current_group[-1][0]) < 5:  # Même position X (tolérance 5 points)
                        current_group.append(line)
                    else:
                        if current_group:
                            v_groups.append(current_group)
                        current_group = [line]
                except (IndexError, TypeError):
                    continue

            if current_group:
                v_groups.append(current_group)

            # Si on a au moins 2 lignes horizontales et 2 verticales, c'est probablement un tableau
            if len(h_groups) >= 2 and len(v_groups) >= 2:
                try:
                    # Calculer le bbox du tableau
                    all_h = [l for group in h_groups for l in group]
                    all_v = [l for group in v_groups for l in group]

                    if not all_h or not all_v:
                        return tables

                    min_x = min(l[0] for l in all_h + all_v)
                    max_x = max(l[2] for l in all_h + all_v)
                    min_y = min(l[1] for l in all_h + all_v)
                    max_y = max(l[3] for l in all_h + all_v)

                    bbox = [min_x, min_y, max_x, max_y]

                    # Extraire le texte dans chaque cellule
                    rows = self._extract_table_cells(page, h_groups, v_groups)

                    if rows:
                        tables.append({
                            'rows': rows,
                            'bbox': bbox,
                            'num_rows': len(h_groups) - 1,
                            'num_cols': len(v_groups) - 1,
                            'type': 'grid'
                        })
                except Exception as e:
                    logger.warning(f"Erreur lors du calcul du tableau: {e}")

        except Exception as e:
            logger.error(f"Erreur dans _detect_tables_from_lines: {e}")

        return tables

    def _extract_table_cells(self, page, h_groups, v_groups) -> List[List[str]]:
        """
        Extrait le texte de chaque cellule d'un tableau.
        """
        rows = []

        try:
            if not h_groups or not v_groups:
                return rows

            # Obtenir les positions Y des lignes horizontales
            try:
                h_positions = sorted(set(g[0][1] for g in h_groups if g and len(g) > 0))
            except (IndexError, TypeError, KeyError) as e:
                logger.warning(f"Erreur lors de l'extraction des positions horizontales: {e}")
                return rows

            # Obtenir les positions X des lignes verticales
            try:
                v_positions = sorted(set(g[0][0] for g in v_groups if g and len(g) > 0))
            except (IndexError, TypeError, KeyError) as e:
                logger.warning(f"Erreur lors de l'extraction des positions verticales: {e}")
                return rows

            if len(h_positions) < 2 or len(v_positions) < 2:
                return rows

            # Pour chaque cellule définie par les intersections
            for i in range(len(h_positions) - 1):
                row = []
                try:
                    y_top = h_positions[i]
                    y_bottom = h_positions[i + 1]

                    for j in range(len(v_positions) - 1):
                        try:
                            x_left = v_positions[j]
                            x_right = v_positions[j + 1]

                            # Extraire le texte dans cette région
                            cell_rect = fitz.Rect(x_left, y_top, x_right, y_bottom)
                            cell_text = page.get_textbox(cell_rect).strip()
                            row.append(cell_text)
                        except Exception as e:
                            # En cas d'erreur, ajouter une cellule vide
                            row.append('')

                    if any(cell for cell in row):  # Ajouter seulement si la ligne contient du texte
                        rows.append(row)
                except (IndexError, TypeError) as e:
                    continue

        except Exception as e:
            logger.error(f"Erreur dans _extract_table_cells: {e}")

        return rows

    def _detect_tables_from_text_alignment(self, page) -> List[Dict[str, Any]]:
        """
        Détecte les tableaux en analysant l'alignement du texte en colonnes.
        """
        tables = []

        try:
            text_dict = page.get_text("dict")

            # Regrouper les blocs par zones verticales proches
            all_words = []
            for block in text_dict.get("blocks", []):
                try:
                    if block.get("type") != 0:
                        continue

                    for line in block.get("lines", []):
                        try:
                            bbox_line = line.get('bbox', [0, 0, 0, 0])
                            if not bbox_line or len(bbox_line) < 4:
                                continue

                            y = bbox_line[1]

                            for span in line.get("spans", []):
                                try:
                                    bbox = span.get('bbox', [0, 0, 0, 0])
                                    if not bbox or len(bbox) < 4:
                                        continue

                                    text = span.get('text', '').strip()
                                    if text:
                                        all_words.append({
                                            'text': text,
                                            'bbox': bbox,
                                            'x': bbox[0],
                                            'y': bbox[1]
                                        })
                                except (IndexError, TypeError, KeyError):
                                    continue
                        except (IndexError, TypeError, KeyError):
                            continue
                except (IndexError, TypeError, KeyError):
                    continue

            if not all_words:
                return tables

            # Trier par Y (ligne)
            try:
                all_words.sort(key=lambda w: (round(w['y'] / 5) * 5, w['x']))
            except (TypeError, KeyError):
                return tables

            # Regrouper en lignes
            lines = []
            current_line = [all_words[0]]

            for word in all_words[1:]:
                try:
                    if abs(word['y'] - current_line[0]['y']) < 5:
                        current_line.append(word)
                    else:
                        if len(current_line) >= 2:  # Au moins 2 colonnes
                            lines.append(current_line)
                        current_line = [word]
                except (KeyError, TypeError, IndexError):
                    continue

            if len(current_line) >= 2:
                lines.append(current_line)

            # Détecter des groupes de lignes avec le même nombre de colonnes
            if len(lines) >= 2:
                try:
                    # Analyser les positions X pour détecter les colonnes
                    x_positions = set()
                    for line in lines:
                        for word in line:
                            try:
                                x_positions.add(round(word['x'] / 10) * 10)
                            except (KeyError, TypeError):
                                continue

                    # Si on a plusieurs colonnes alignées
                    if len(x_positions) >= 2:
                        x_sorted = sorted(x_positions)

                        # Essayer de créer un tableau
                        rows = []
                        for line in lines:
                            try:
                                # Assigner chaque mot à une colonne
                                row = [''] * len(x_sorted)
                                for word in line:
                                    try:
                                        x_rounded = round(word['x'] / 10) * 10
                                        col_idx = x_sorted.index(x_rounded)
                                        row[col_idx] = word['text']
                                    except (ValueError, KeyError, TypeError):
                                        pass

                                rows.append(row)
                            except Exception:
                                continue

                        if len(rows) >= 2:
                            try:
                                # Calculer le bbox
                                all_bboxes = [w['bbox'] for line in lines for w in line if 'bbox' in w]
                                if all_bboxes:
                                    min_x = min(b[0] for b in all_bboxes)
                                    min_y = min(b[1] for b in all_bboxes)
                                    max_x = max(b[2] for b in all_bboxes)
                                    max_y = max(b[3] for b in all_bboxes)

                                    tables.append({
                                        'rows': rows,
                                        'bbox': [min_x, min_y, max_x, max_y],
                                        'num_rows': len(rows),
                                        'num_cols': len(x_sorted),
                                        'type': 'aligned'
                                    })
                            except (ValueError, IndexError):
                                pass
                except Exception as e:
                    logger.warning(f"Erreur lors de la détection des colonnes: {e}")

        except Exception as e:
            logger.error(f"Erreur dans _detect_tables_from_text_alignment: {e}")

        return tables

    def _boxes_overlap(self, bbox1, bbox2, threshold=0.5) -> bool:
        """
        Vérifie si deux boîtes se chevauchent avec un seuil donné.
        """
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2

        # Calculer l'intersection
        x_overlap = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
        y_overlap = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))

        if x_overlap == 0 or y_overlap == 0:
            return False

        intersection_area = x_overlap * y_overlap
        bbox1_area = (x1_max - x1_min) * (y1_max - y1_min)
        bbox2_area = (x2_max - x2_min) * (y2_max - y2_min)

        # Vérifier si le chevauchement dépasse le seuil
        overlap_ratio = intersection_area / min(bbox1_area, bbox2_area)
        return overlap_ratio >= threshold

    def extract_as_html(self) -> str:
        """
        Extrait le contenu du PDF en HTML avec préservation du formatage.

        Returns:
            Contenu HTML du document
        """
        html_parts = ['<!DOCTYPE html>', '<html>', '<head>',
                      '<meta charset="UTF-8">',
                      '<style>body { font-family: Arial, sans-serif; padding: 20px; }</style>',
                      '</head>', '<body>']

        full_data = self.extract_full_document()

        for page in full_data['pages']:
            html_parts.append(f'<div class="page" data-page="{page["page_number"]}">')
            html_parts.append(f'<h2>Page {page["page_number"]}</h2>')

            # Ajouter le texte
            for block in page.get('text_blocks', []):
                html_parts.append('<div class="text-block">')
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        text = span.get('text', '').replace('<', '&lt;').replace('>', '&gt;')

                        # Créer les styles
                        styles = []
                        if span.get('size'):
                            styles.append(f"font-size: {span['size']}px")
                        if span.get('color') and span['color'] != '#000000':
                            styles.append(f"color: {span['color']}")

                        # Créer les balises
                        if span.get('bold'):
                            text = f'<strong>{text}</strong>'
                        if span.get('italic'):
                            text = f'<em>{text}</em>'

                        if styles:
                            text = f'<span style="{"; ".join(styles)}">{text}</span>'

                        html_parts.append(text)
                    html_parts.append('<br>')
                html_parts.append('</div>')

            # Ajouter les images
            for img in page.get('images', []):
                html_parts.append(f'<img src="{img["data"]}" width="{img["width"]}" height="{img["height"]}" />')

            html_parts.append('</div>')

        html_parts.extend(['</body>', '</html>'])
        return '\n'.join(html_parts)

    @staticmethod
    def _int_to_rgb_hex(color_int: int) -> str:
        """
        Convertit un entier de couleur en format hexadécimal RGB.

        Args:
            color_int: Couleur en format entier

        Returns:
            Couleur en format hex (#RRGGBB)
        """
        # PyMuPDF stocke les couleurs au format 0xRRGGBB
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return f'#{r:02x}{g:02x}{b:02x}'

class PDFToEditableConverter:
    """
    Convertit un PDF en format éditable pour l'éditeur.
    Supporte les formats Quill Delta et Fabric.js.
    """
    @staticmethod
    def convert_to_quill_delta(pdf_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Convertit les données PDF extraites en format Quill Delta.
        Préserve fidèlement le formatage du document original.

        Args:
            pdf_data: Données extraites du PDF (via extract_full_document)

        Returns:
            Dict avec 'ops' contenant les opérations Quill Delta
        """
        ops = []

        for page in pdf_data.get('pages', []):
            # En-tête de page avec style
            ops.append({
                'insert': f"Page {page['page_number']}",
                'attributes': {
                    'bold': True,
                    'color': '#667eea',
                    'size': '16px'
                }
            })
            ops.append({'insert': '\n', 'attributes': {'align': 'center'}})
            ops.append({'insert': '\n'})  # Ligne vide après l'en-tête

            # Traiter les blocs de texte
            for block in page.get('text_blocks', []):
                for line in block.get('lines', []):
                    line_text_added = False

                    for span in line.get('spans', []):
                        text = span.get('text', '')
                        if not text:
                            continue

                        # Construire les attributs de formatage
                        attributes = {}
                        if span.get('bold'):
                            attributes['bold'] = True
                        if span.get('italic'):
                            attributes['italic'] = True

                        # Ajouter la couleur seulement si différente du noir
                        color = span.get('color', '#000000')
                        if color and color != '#000000':
                            attributes['color'] = color

                        # Ajouter la taille de police
                        size = span.get('size')
                        if size:
                            # Arrondir et convertir en pixels
                            attributes['size'] = f"{int(round(size))}px"

                        # Ajouter la police si disponible
                        font = span.get('font', '')
                        if font:
                            # Extraire le nom de base de la police
                            font_name = font.split('+')[-1].split('-')[0]
                            attributes['font'] = font_name

                        # Ajouter l'opération avec ou sans attributs
                        if attributes:
                            ops.append({
                                'insert': text,
                                'attributes': attributes
                            })
                        else:
                            ops.append({'insert': text})

                        line_text_added = True

                    # Ajouter un retour à la ligne après chaque ligne de texte
                    if line_text_added:
                        ops.append({'insert': '\n'})

                # Petite séparation entre les blocs
                if block.get('lines'):
                    ops.append({'insert': '\n'})

            # Traiter les images
            for img in page.get('images', []):
                try:
                    # Calculer une taille d'affichage raisonnable
                    width = img.get('width', 100)
                    height = img.get('height', 100)

                    # Limiter la taille maximale tout en gardant le ratio
                    max_width = 600
                    if width > max_width:
                        ratio = max_width / width
                        width = max_width
                        height = int(height * ratio)

                    ops.append({
                        'insert': {'image': img['data']},
                        'attributes': {
                            'width': str(width),
                            'height': str(height)
                        }
                    })
                    ops.append({'insert': '\n'})
                except Exception as e:
                    logger.warning(f"Erreur lors de l'ajout de l'image: {e}")
                    continue

            # Traiter les tableaux
            for table in page.get('tables', []):
                try:
                    # Ajouter un indicateur de tableau
                    ops.append({
                        'insert': '📊 Tableau détecté:\n',
                        'attributes': {'bold': True, 'color': '#4a5568'}
                    })

                    for row in table.get('rows', []):
                        # Joindre les cellules avec des séparateurs
                        row_text = ' | '.join(str(cell) for cell in row)
                        ops.append({'insert': row_text + '\n'})

                    ops.append({'insert': '\n'})
                except Exception as e:
                    logger.warning(f"Erreur lors de l'ajout du tableau: {e}")
                    continue

            # Séparateur entre les pages
            if page['page_number'] < pdf_data.get('total_pages', 1):
                ops.append({'insert': '\n' + '─' * 50 + '\n\n'})

        return {'ops': ops}

    @staticmethod
    def convert_to_fabric_objects(pdf_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convertit les données PDF extraites en objets Fabric.js.
        Reproduction FIDÈLE du document PDF avec positions exactes.

        Args:
            pdf_data: Données extraites du PDF (via extract_full_document)

        Returns:
            Dict avec les objets Fabric.js positionnés fidèlement
        """
        fabric_objects = []
        page_spacing = 50  # Espacement entre les pages
        scale_factor = 1.5  # Facteur d'agrandissement pour meilleure lisibilité

        for page_idx, page in enumerate(pdf_data.get('pages', [])):
            page_width = page.get('width', 595) * scale_factor
            page_height = page.get('height', 842) * scale_factor
            page_y_offset = page_idx * (page_height + page_spacing)

            # Fond de page avec bordure
            fabric_objects.append({
                'type': 'rect',
                'left': 0,
                'top': page_y_offset,
                'width': page_width,
                'height': page_height,
                'fill': '#ffffff',
                'stroke': '#cbd5e0',
                'strokeWidth': 1,
                'selectable': False,
                'evented': False,
                'shadow': {
                    'color': 'rgba(0,0,0,0.1)',
                    'blur': 10,
                    'offsetX': 0,
                    'offsetY': 2
                }
            })

            # Indicateur de page (petit badge)
            fabric_objects.append({
                'type': 'text',
                'text': f'{page["page_number"]}',
                'left': page_width - 45,
                'top': page_y_offset + 15,
                'fontSize': 12,
                'fontWeight': 'bold',
                'fill': '#a0aec0',
                'fontFamily': 'Arial',
                'selectable': False,
                'evented': False,
                'originX': 'center',
                'originY': 'top'
            })

            # IMPORTANT: Traiter les TABLEAUX EN PREMIER pour qu'ils soient en arrière-plan
            # Les textes seront ajoutés par-dessus (ordre Z important dans Fabric.js)
            for table in page.get('tables', []):
                bbox = table.get('bbox', [0, 0, 0, 0])
                rows = table.get('rows', [])

                if not rows:
                    continue

                # Calculer les dimensions du tableau avec facteur d'échelle
                table_left = bbox[0] * scale_factor
                table_top = page_y_offset + (bbox[1] * scale_factor)
                table_width = (bbox[2] - bbox[0]) * scale_factor
                table_height = (bbox[3] - bbox[1]) * scale_factor

                # Utiliser les informations de structure si disponibles
                num_rows = table.get('num_rows', len(rows))
                num_cols = table.get('num_cols', max(len(row) for row in rows) if rows else 1)

                # Assurer que toutes les lignes ont le même nombre de colonnes
                normalized_rows = []
                for row in rows:
                    # Compléter la ligne avec des cellules vides si nécessaire
                    normalized_row = list(row) + [''] * (num_cols - len(row))
                    normalized_rows.append(normalized_row[:num_cols])

                # Calculer les dimensions des cellules
                cell_height = table_height / num_rows if num_rows > 0 else 20
                cell_width = table_width / num_cols if num_cols > 0 else 100

                # Fond du tableau TRANSPARENT pour voir les textes du document original
                # On garde seulement les bordures pour délimiter le tableau
                fabric_objects.append({
                    'type': 'rect',
                    'left': table_left,
                    'top': table_top,
                    'width': table_width,
                    'height': table_height,
                    'fill': 'rgba(255, 255, 255, 0.05)',  # Presque transparent, juste une légère teinte
                    'stroke': '#2d3748',
                    'strokeWidth': 2,
                    'selectable': False,
                    'evented': False,
                    'originX': 'left',
                    'originY': 'top'
                })

                # Dessiner les lignes horizontales du tableau
                for i in range(num_rows + 1):
                    y = table_top + (i * cell_height)
                    # Ligne plus épaisse pour l'en-tête
                    stroke_width = 2 if i == 1 else 1
                    fabric_objects.append({
                        'type': 'line',
                        'x1': table_left,
                        'y1': y,
                        'x2': table_left + table_width,
                        'y2': y,
                        'stroke': '#2d3748' if i in [0, 1] else '#cbd5e0',
                        'strokeWidth': stroke_width,
                        'selectable': False,
                        'evented': False
                    })

                # Dessiner les lignes verticales du tableau
                for j in range(num_cols + 1):
                    x = table_left + (j * cell_width)
                    fabric_objects.append({
                        'type': 'line',
                        'x1': x,
                        'y1': table_top,
                        'x2': x,
                        'y2': table_top + table_height,
                        'stroke': '#2d3748' if j in [0, num_cols] else '#cbd5e0',
                        'strokeWidth': 1,
                        'selectable': False,
                        'evented': False
                    })

                # NE PAS ajouter le contenu des cellules manuellement
                # Le texte original du PDF sera visible à travers le tableau transparent
                # Cela garantit la fidélité au document original

                # Fond légèrement coloré pour la première ligne (en-tête) si besoin
                for col_idx in range(num_cols):
                    fabric_objects.append({
                        'type': 'rect',
                        'left': table_left + (col_idx * cell_width) + 1,
                        'top': table_top + 1,
                        'width': cell_width - 2,
                        'height': cell_height - 2,
                        'fill': 'rgba(237, 242, 247, 0.2)',  # Très léger fond pour l'en-tête
                        'stroke': 'transparent',
                        'strokeWidth': 0,
                        'selectable': False,
                        'evented': False,
                        'originX': 'left',
                        'originY': 'top'
                    })

            # Traiter les blocs de texte APRÈS les tableaux pour qu'ils soient par-dessus
            # REGROUPER par LIGNE pour éviter des centaines de petits objets
            for block in page.get('text_blocks', []):
                for line in block.get('lines', []):
                    spans = line.get('spans', [])
                    if not spans:
                        continue

                    # Regrouper tous les spans de la ligne en un seul texte
                    line_text_parts = []
                    line_bbox = line.get('bbox', [0, 0, 0, 0])

                    # Déterminer les propriétés dominantes de la ligne (premier span)
                    first_span = spans[0]
                    dominant_font_size = first_span.get('size', 12)
                    dominant_bold = first_span.get('bold', False)
                    dominant_italic = first_span.get('italic', False)
                    dominant_color = first_span.get('color', '#000000')
                    dominant_font = first_span.get('font', '')

                    # Concaténer tous les textes de la ligne
                    for span in spans:
                        text = span.get('text', '')
                        if text:
                            line_text_parts.append(text)

                    if not line_text_parts:
                        continue

                    full_line_text = ''.join(line_text_parts)
                    if not full_line_text.strip():
                        continue

                    # Calculer la position de la ligne avec facteur d'échelle
                    left = line_bbox[0] * scale_factor
                    top = page_y_offset + (line_bbox[1] * scale_factor)
                    width = (line_bbox[2] - line_bbox[0]) * scale_factor
                    height = (line_bbox[3] - line_bbox[1]) * scale_factor

                    # Déterminer la police avec fallback
                    font_family = 'Arial'  # Défaut
                    if dominant_font:
                        # Nettoyer le nom de la police
                        font_clean = dominant_font.split('+')[-1].split('-')[0]
                        # Mapper vers des polices web standard
                        if 'Times' in font_clean or 'Serif' in font_clean:
                            font_family = 'Times New Roman'
                        elif 'Courier' in font_clean or 'Mono' in font_clean:
                            font_family = 'Courier New'
                        elif 'Helvetica' in font_clean or 'Arial' in font_clean:
                            font_family = 'Arial'
                        else:
                            font_family = font_clean

                    # Créer UN SEUL objet texte par ligne (beaucoup plus organisé)
                    fabric_objects.append({
                        'type': 'text',
                        'text': full_line_text,
                        'left': left,
                        'top': top,
                        'fontSize': dominant_font_size * scale_factor,
                        'fontWeight': 'bold' if dominant_bold else 'normal',
                        'fontStyle': 'italic' if dominant_italic else 'normal',
                        'fill': dominant_color,
                        'fontFamily': font_family,
                        'selectable': True,
                        'editable': True,
                        'originX': 'left',
                        'originY': 'top',
                        'lineHeight': 1.2,
                        'charSpacing': 0
                    })

            # Traiter les images avec position FIDÈLE et facteur d'échelle
            for img in page.get('images', []):
                bbox = img.get('bbox', [0, 0, 100, 100])

                # bbox format: [x0, y0, x1, y1] ou Rect
                if hasattr(bbox, 'x0'):
                    left = bbox.x0 * scale_factor
                    top = bbox.y0 * scale_factor
                    width = (bbox.x1 - bbox.x0) * scale_factor
                    height = (bbox.y1 - bbox.y0) * scale_factor
                else:
                    left = bbox[0] * scale_factor
                    top = bbox[1] * scale_factor
                    width = ((bbox[2] - bbox[0]) if len(bbox) > 2 else img.get('width', 100)) * scale_factor
                    height = ((bbox[3] - bbox[1]) if len(bbox) > 3 else img.get('height', 100)) * scale_factor

                fabric_objects.append({
                    'type': 'image',
                    'src': img['data'],
                    'left': left,
                    'top': page_y_offset + top,
                    'width': width,
                    'height': height,
                    'selectable': True,
                    'hasControls': True,
                    'hasBorders': True,
                    'originX': 'left',
                    'originY': 'top',
                    'crossOrigin': 'anonymous'
                })

        # Calculer la hauteur totale du canvas avec scale_factor
        num_pages = len(pdf_data.get('pages', []))
        if num_pages > 0:
            # Utiliser la hauteur de la première page (généralement toutes les pages ont la même hauteur)
            first_page = pdf_data['pages'][0]
            page_height_scaled = first_page.get('height', 842) * scale_factor
            # Formule: (nombre_pages - 1) × (hauteur_page + espacement) + hauteur_dernière_page + marge_finale
            canvas_height = (num_pages - 1) * (page_height_scaled + page_spacing) + page_height_scaled + 50
        else:
            canvas_height = 1200

        # Largeur agrandie pour afficher tout le contenu (facteur d'échelle 1.5x)
        # Convertir de points PDF (595pt pour A4) vers pixels affichage (900px)
        if pdf_data.get('pages'):
            pdf_width = max(page.get('width', 595) for page in pdf_data.get('pages', []))
            # Échelle d'agrandissement pour meilleure lisibilité
            canvas_width = int(pdf_width * 1.5)  # 595 * 1.5 ≈ 892px
            if canvas_width < 900:
                canvas_width = 900
        else:
            canvas_width = 900

        return {
            'version': '5.3.0',
            'objects': fabric_objects,
            'background': '#e2e8f0',
            'canvasHeight': canvas_height,
            'canvasWidth': canvas_width
        }
