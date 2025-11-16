# FICHIER: database_manager/services.py
# SERVICES POUR LA GÉNÉRATION DE SCHÉMAS DE BASE DE DONNÉES
# ============================================

from django.conf import settings
import json
from .models import DatabaseSchema, DatabaseTable, DatabaseField, DataExtraction
from documents.models import Document, DocumentAnalysis, DocumentChunk

# Import Groq pour la génération de schémas
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class SchemaGenerator:
    """Service de génération automatique de schémas de base de données"""

    def __init__(self):
        if GROQ_AVAILABLE and hasattr(settings, 'GROQ_API_KEY') and settings.GROQ_API_KEY:
            self.client = Groq(api_key=settings.GROQ_API_KEY)
        else:
            self.client = None

    def generate_schema_from_document(self, document, user):
        """
        Génère un schéma de base de données à partir d'un document analysé
        """
        try:
            # Récupérer le contenu et l'analyse du document
            content = document.content
            analysis = document.analysis

            # Créer le prompt pour l'IA
            prompt = f"""
Analyse ce document et génère une structure de base de données relationnelle adaptée.

Résumé du document: {analysis.summary[:1000]}

Mots-clés: {', '.join(analysis.keywords[:20])}

Entités identifiées: {json.dumps(analysis.entities, ensure_ascii=False)[:500]}

Extrait du contenu:
{content.raw_text[:3000]}

Fournis un schéma de base de données complet en JSON avec cette structure:
{{
    "schema_name": "nom_du_schema",
    "description": "description du schéma",
    "tables": [
        {{
            "name": "nom_table",
            "description": "description de la table",
            "fields": [
                {{
                    "name": "nom_champ",
                    "type": "varchar|text|integer|bigint|decimal|float|boolean|date|datetime|json",
                    "max_length": 255,  // optionnel
                    "nullable": true,
                    "unique": false,
                    "primary_key": false,
                    "description": "description du champ"
                }}
            ],
            "foreign_keys": [
                {{
                    "field": "nom_champ",
                    "references_table": "nom_table_reference",
                    "references_field": "id",
                    "on_delete": "CASCADE|SET_NULL|RESTRICT",
                    "relation_type": "one_to_one|one_to_many|many_to_many",
                    "description": "description de la relation"
                }}
            ]
        }}
    ],
    "relations_analysis": "Analyse détaillée des relations identifiées entre les entités"
}}

Règles importantes:
1. Chaque table doit avoir une clé primaire 'id' de type integer avec primary_key: true
2. Utilise des noms de tables et champs en snake_case (minuscules avec _)
3. Ajoute created_at et updated_at (datetime) à chaque table
4. **ANALYSE ATTENTIVEMENT LES RELATIONS**: Identifie toutes les relations entre entités du document
5. Pour chaque relation, détermine le type exact:
   - one_to_one: relation 1:1 (ex: User ↔ Profile)
   - one_to_many: relation 1:N (ex: User → Orders, une commande a UN user)
   - many_to_many: relation N:N (nécessite une table de jonction)
6. Les clés étrangères doivent suivre la convention: nom_table_singulier_id (ex: user_id, product_id)
7. Pour les FK nullable, mettre nullable: true (relation optionnelle, cardinalité 0..1)
8. Pour les FK non nullable, mettre nullable: false (relation obligatoire, cardinalité 1)
9. Nomme les tables au PLURIEL (users, products, orders) sauf pour les tables de jonction
10. Pour les tables de jonction many-to-many, utilise le format: table1_table2 (ex: users_roles)
11. Limite à 10 tables maximum pour rester gérable
12. Ajoute un champ "relations_analysis" expliquant les relations détectées

EXEMPLES DE RELATIONS:
- Client → Commandes (one_to_many): Le champ "client_id" dans la table "commandes" référence "clients"
- Produit ↔ Catégories (many_to_many): Table de jonction "produits_categories" avec "produit_id" et "categorie_id"
- User → Profile (one_to_one): Le champ "user_id" dans "profiles" avec contrainte unique

Réponds uniquement avec un JSON valide, sans texte additionnel.
"""

            # Appeler l'API Groq
            print(f"[DEBUG Schema] Appel à Groq pour génération de schéma...")
            response = self.client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un expert en modélisation de bases de données relationnelles. Tu dois TOUJOURS répondre UNIQUEMENT avec un JSON valide, sans texte avant ou après."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=4000
            )

            result_text = response.choices[0].message.content
            print(f"[DEBUG Schema] Réponse de Groq (longueur: {len(result_text)}):")
            print(f"[DEBUG Schema] Premiers 500 caractères: {result_text[:500]}")

            # Nettoyer la réponse pour extraire le JSON
            # Parfois Groq ajoute du texte avant/après le JSON
            result_text = result_text.strip()

            # Trouver le début et la fin du JSON
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("Aucun JSON trouvé dans la réponse de Groq")

            json_text = result_text[json_start:json_end]
            print(f"[DEBUG Schema] JSON extrait (longueur: {len(json_text)})")

            # Parser le JSON
            schema_data = json.loads(json_text)

            # Créer le schéma en base de données
            schema = DatabaseSchema.objects.create(
                document=document,
                name=schema_data.get('schema_name', f'schema_{document.title}'),
                description=schema_data.get('description', ''),
                schema_definition=schema_data,
                status='proposed'
            )

            # Créer les tables et champs
            self._create_tables_from_schema(schema, schema_data)

            return schema

        except Exception as e:
            print(f"[ERREUR Schema] Type: {type(e).__name__}")
            print(f"[ERREUR Schema] Message: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _create_tables_from_schema(self, schema, schema_data):
        """Crée les définitions de tables et de champs à partir du JSON"""
        from .models import DatabaseRelation
        tables_map = {}  # Pour mapper les noms de tables aux objets
        fields_map = {}  # Pour mapper les champs par table et nom

        # Première passe: créer les tables
        for table_data in schema_data.get('tables', []):
            table = DatabaseTable.objects.create(
                schema=schema,
                name=table_data['name'],
                description=table_data.get('description', '')
            )
            tables_map[table_data['name']] = table
            fields_map[table_data['name']] = {}

        # Deuxième passe: créer les champs
        for table_data in schema_data.get('tables', []):
            table = tables_map[table_data['name']]

            for i, field_data in enumerate(table_data.get('fields', [])):
                field = DatabaseField.objects.create(
                    table=table,
                    name=field_data['name'],
                    field_type=field_data['type'],
                    max_length=field_data.get('max_length'),
                    is_nullable=field_data.get('nullable', True),
                    is_unique=field_data.get('unique', False),
                    is_primary_key=field_data.get('primary_key', False),
                    description=field_data.get('description', ''),
                    order=i
                )
                fields_map[table_data['name']][field_data['name']] = field

        # Troisième passe: ajouter les clés étrangères comme relations
        for table_data in schema_data.get('tables', []):
            table = tables_map[table_data['name']]

            for fk_data in table_data.get('foreign_keys', []):
                field_name = fk_data['field']
                ref_table_name = fk_data['references_table']
                ref_field_name = fk_data.get('references_field', 'id')
                relation_type = fk_data.get('relation_type', 'one_to_many')
                fk_description = fk_data.get('description', '')
                is_nullable = fk_data.get('nullable', True)

                if ref_table_name in tables_map:
                    # Créer ou récupérer le champ de clé étrangère
                    if field_name in fields_map[table_data['name']]:
                        # Le champ existe déjà, le mettre à jour
                        fk_field = fields_map[table_data['name']][field_name]
                        fk_field.field_type = 'foreign_key'
                        fk_field.is_nullable = is_nullable
                        fk_field.save()
                    else:
                        # Créer le champ de clé étrangère
                        fk_field = DatabaseField.objects.create(
                            table=table,
                            name=field_name,
                            field_type='foreign_key',
                            is_nullable=is_nullable,
                            description=fk_description,
                            order=len(fields_map[table_data['name']])
                        )
                        fields_map[table_data['name']][field_name] = fk_field

                    # Trouver le champ référencé
                    ref_field = None
                    if ref_field_name in fields_map.get(ref_table_name, {}):
                        ref_field = fields_map[ref_table_name][ref_field_name]

                    # Créer la relation
                    DatabaseRelation.objects.create(
                        schema=schema,
                        from_table=table,
                        to_table=tables_map[ref_table_name],
                        from_field=fk_field,
                        to_field=ref_field,
                        relation_type=relation_type,
                        description=fk_description
                    )

        print(f"[DEBUG Schema] Schéma créé: {len(tables_map)} tables, {DatabaseRelation.objects.filter(schema=schema).count()} relations")


class SQLGenerator:
    """Service de génération de code SQL"""

    def generate_sql_from_schema(self, schema):
        """Génère le SQL pour créer les tables du schéma"""
        sql_statements = []

        # Entête
        sql_statements.append(f"-- Schéma: {schema.name}")
        sql_statements.append(f"-- Description: {schema.description}")
        sql_statements.append(f"-- Généré le: {schema.created_at}")
        sql_statements.append("")

        # Créer les tables dans l'ordre (en gérant les dépendances)
        tables = schema.tables.all()

        for table in tables:
            sql = self._generate_table_sql(table)
            sql_statements.append(sql)
            sql_statements.append("")

        # Retourner le SQL généré
        full_sql = "\n".join(sql_statements)
        return full_sql

    def _generate_table_sql(self, table):
        """Génère le SQL pour une table"""
        lines = []
        lines.append(f"CREATE TABLE {table.name} (")

        fields = table.fields.all()
        field_lines = []

        for field in fields:
            field_def = self._generate_field_sql(field)
            field_lines.append(f"    {field_def}")

        # Ajouter les contraintes de clés étrangères via les relations
        from .models import DatabaseRelation
        relations = DatabaseRelation.objects.filter(from_table=table)
        for rel in relations:
            if rel.from_field and rel.to_table:
                fk_constraint = f"    FOREIGN KEY ({rel.from_field.name}) REFERENCES {rel.to_table.name}(id)"
                field_lines.append(fk_constraint)

        lines.append(",\n".join(field_lines))
        lines.append(");")

        return "\n".join(lines)

    def _generate_field_sql(self, field):
        """Génère le SQL pour un champ"""
        parts = [field.name]

        # Type de données
        if field.field_type == 'varchar':
            max_len = field.max_length or 255
            parts.append(f"VARCHAR({max_len})")
        elif field.field_type == 'text':
            parts.append("TEXT")
        elif field.field_type == 'integer' or field.field_type == 'foreign_key':
            parts.append("INTEGER")
        elif field.field_type == 'bigint':
            parts.append("BIGINT")
        elif field.field_type == 'decimal':
            parts.append("DECIMAL(10, 2)")
        elif field.field_type == 'float':
            parts.append("FLOAT")
        elif field.field_type == 'boolean':
            parts.append("BOOLEAN")
        elif field.field_type == 'date':
            parts.append("DATE")
        elif field.field_type == 'datetime':
            parts.append("TIMESTAMP")
        elif field.field_type == 'json':
            parts.append("JSON")

        # Contraintes
        if field.is_primary_key:
            parts.append("PRIMARY KEY")

        if not field.is_nullable:
            parts.append("NOT NULL")

        if field.is_unique:
            parts.append("UNIQUE")

        if field.default_value:
            parts.append(f"DEFAULT '{field.default_value}'")

        return " ".join(parts)


class DataExtractionService:
    """Service d'extraction automatique de données depuis un document"""

    def __init__(self):
        if GROQ_AVAILABLE and hasattr(settings, 'GROQ_API_KEY') and settings.GROQ_API_KEY:
            self.client = Groq(api_key=settings.GROQ_API_KEY)
        else:
            self.client = None

    def extract_data_from_document(self, schema, document):
        """
        Extrait les données d'un document pour remplir un schéma de base de données validé

        Args:
            schema: DatabaseSchema validé
            document: Document à analyser

        Returns:
            DataExtraction object avec les données extraites en JSON
        """
        try:
            print(f"[DEBUG DataExtraction] Début extraction pour {document.title} → {schema.name}")

            # Vérifier que le schéma est validé
            if schema.status != 'validated':
                raise ValueError("Le schéma doit être validé avant l'extraction de données")

            # Récupérer le contenu du document
            content = document.content
            analysis = document.analysis

            # Récupérer tous les chunks pour avoir plus de contexte
            chunks = DocumentChunk.objects.filter(document=document).order_by('chunk_index')

            # Construire le texte complet (limité pour ne pas dépasser les limites de l'API)
            full_text = content.raw_text[:20000]  # Limiter à 20000 caractères

            # Si on a des chunks, les utiliser aussi
            if chunks.exists():
                chunk_texts = [chunk.content for chunk in chunks[:30]]  # Max 30 chunks
                chunks_text = "\n\n---\n\n".join(chunk_texts)
                full_text = chunks_text[:20000]  # Prioriser les chunks si disponibles

            print(f"[DEBUG DataExtraction] Texte du document: {len(full_text)} caractères")

            # Construire la description du schéma pour le prompt
            schema_description = self._build_schema_description(schema)

            print(f"[DEBUG DataExtraction] Description du schéma: {len(schema_description)} caractères")

            # Créer le prompt pour l'extraction
            prompt = f"""
Tu es un expert en extraction de données structurées.

SCHÉMA DE BASE DE DONNÉES CIBLE:
{schema_description}

DOCUMENT À ANALYSER:
Titre: {document.title}
Résumé: {analysis.summary[:500] if analysis else 'N/A'}

Contenu du document:
{full_text}

TÂCHE:
Extrait toutes les données pertinentes du document et structure-les selon le schéma de base de données fourni.

INSTRUCTIONS IMPORTANTES:
1. Génère un JSON avec une clé pour chaque table du schéma
2. Pour chaque table, fournis un tableau d'objets représentant les lignes à insérer
3. Chaque objet doit avoir les champs définis dans le schéma (sauf 'id', 'created_at', 'updated_at' qui seront auto-générés)
4. Si une donnée n'est pas présente dans le document, utilise null
5. Pour les clés étrangères, utilise des identifiants cohérents (par exemple: 1, 2, 3...)
6. Extrais le maximum d'informations pertinentes du document
7. Ajoute un champ "_notes" pour chaque table avec des commentaires sur l'extraction
8. Ajoute un champ "_confidence" (0-1) pour chaque table indiquant ta confiance dans l'extraction

FORMAT DE RÉPONSE ATTENDU:
{{
    "tables": {{
        "nom_table_1": {{
            "rows": [
                {{"champ1": "valeur1", "champ2": "valeur2", ...}},
                {{"champ1": "valeur3", "champ2": "valeur4", ...}}
            ],
            "_notes": "Commentaires sur cette extraction",
            "_confidence": 0.95
        }},
        "nom_table_2": {{
            "rows": [...],
            "_notes": "...",
            "_confidence": 0.85
        }}
    }},
    "global_notes": "Notes globales sur l'extraction",
    "global_confidence": 0.90
}}

Réponds UNIQUEMENT avec le JSON, sans texte avant ou après.
"""

            print(f"[DEBUG DataExtraction] Prompt créé: {len(prompt)} caractères")
            print(f"[DEBUG DataExtraction] Appel à Groq pour extraction...")

            # Appeler l'API Groq
            response = self.client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un expert en extraction de données structurées. Tu dois TOUJOURS répondre UNIQUEMENT avec un JSON valide, sans texte avant ou après."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,  # Basse température pour plus de précision
                max_tokens=6000  # Plus de tokens pour des données complexes
            )

            result_text = response.choices[0].message.content
            print(f"[DEBUG DataExtraction] Réponse de Groq (longueur: {len(result_text)})")
            print(f"[DEBUG DataExtraction] Premiers 300 caractères: {result_text[:300]}")

            # Nettoyer et extraire le JSON
            result_text = result_text.strip()

            # Trouver le JSON
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("Aucun JSON trouvé dans la réponse de Groq")

            json_text = result_text[json_start:json_end]
            print(f"[DEBUG DataExtraction] JSON extrait (longueur: {len(json_text)})")

            # Parser le JSON
            extracted_data = json.loads(json_text)

            # Calculer le score de confiance global
            global_confidence = extracted_data.get('global_confidence', 0.5)
            global_notes = extracted_data.get('global_notes', '')

            # Créer l'objet DataExtraction
            data_extraction = DataExtraction.objects.create(
                schema=schema,
                document=document,
                extracted_data=extracted_data,
                status='extracted',
                confidence_score=global_confidence,
                extraction_notes=global_notes
            )

            print(f"[DEBUG DataExtraction] Extraction créée avec succès: ID={data_extraction.id}")
            print(f"[DEBUG DataExtraction] Confiance globale: {global_confidence}")

            return data_extraction

        except Exception as e:
            print(f"[ERREUR DataExtraction] Type: {type(e).__name__}")
            print(f"[ERREUR DataExtraction] Message: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def _build_schema_description(self, schema):
        """Construit une description textuelle du schéma pour le prompt"""
        lines = [f"Nom du schéma: {schema.name}"]
        lines.append(f"Description: {schema.description}\n")

        tables = schema.tables.all().prefetch_related('fields', 'relations_from')

        for table in tables:
            lines.append(f"\nTABLE: {table.name}")
            if table.description:
                lines.append(f"  Description: {table.description}")

            lines.append("  Champs:")
            for field in table.fields.all():
                field_info = f"    - {field.name} ({field.field_type})"
                if not field.is_nullable:
                    field_info += " NOT NULL"
                if field.is_primary_key:
                    field_info += " PRIMARY KEY"
                if field.is_unique:
                    field_info += " UNIQUE"
                if field.description:
                    field_info += f" // {field.description}"
                lines.append(field_info)

            # Ajouter les relations
            relations = table.relations_from.all()
            if relations.exists():
                lines.append("  Relations:")
                for rel in relations:
                    lines.append(f"    - {rel.from_field.name if rel.from_field else '?'} → {rel.to_table.name}")

        return "\n".join(lines)

    def generate_insert_sql(self, data_extraction):
        """
        Génère des requêtes SQL INSERT à partir des données extraites

        Args:
            data_extraction: DataExtraction object

        Returns:
            str: SQL INSERT statements
        """
        sql_statements = []

        sql_statements.append(f"-- Données extraites de: {data_extraction.document.title}")
        sql_statements.append(f"-- Schéma: {data_extraction.schema.name}")
        sql_statements.append(f"-- Date d'extraction: {data_extraction.created_at}")
        sql_statements.append(f"-- Confiance: {data_extraction.confidence_score}")
        sql_statements.append("")

        extracted_data = data_extraction.extracted_data
        tables_data = extracted_data.get('tables', {})

        for table_name, table_info in tables_data.items():
            rows = table_info.get('rows', [])

            if not rows:
                continue

            sql_statements.append(f"\n-- Table: {table_name}")
            sql_statements.append(f"-- Notes: {table_info.get('_notes', 'N/A')}")
            sql_statements.append(f"-- Confiance: {table_info.get('_confidence', 'N/A')}")

            for row in rows:
                # Filtrer les champs spéciaux (commençant par _)
                fields = {k: v for k, v in row.items() if not k.startswith('_')}

                if not fields:
                    continue

                field_names = ', '.join(fields.keys())

                # Formater les valeurs
                values = []
                for v in fields.values():
                    if v is None:
                        values.append('NULL')
                    elif isinstance(v, str):
                        # Échapper les apostrophes
                        escaped_v = v.replace("'", "''")
                        values.append(f"'{escaped_v}'")
                    elif isinstance(v, bool):
                        values.append('TRUE' if v else 'FALSE')
                    else:
                        values.append(str(v))

                values_str = ', '.join(values)

                sql_statements.append(f"INSERT INTO {table_name} ({field_names}) VALUES ({values_str});")

        return "\n".join(sql_statements)