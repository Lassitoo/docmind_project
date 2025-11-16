# FICHIER: database_manager/views.py
# VUES POUR LA GESTION DES BASES DE DONNÉES
# ============================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from .models import ExternalDatabase, DatabaseSchema, DatabaseTable, DatabaseField, DataExtraction
from .forms import ExternalDatabaseForm, DatabaseSchemaForm, DatabaseTableForm, DatabaseFieldForm, SchemaValidationForm
from .services import SchemaGenerator, SQLGenerator, DataExtractionService
from documents.models import Document


@login_required
def external_database_list(request):
    """Liste des bases de données externes"""
    databases = ExternalDatabase.objects.filter(user=request.user).order_by('-created_at')

    context = {
        'databases': databases,
    }

    return render(request, 'database_manager/external_database_list.html', context)


@login_required
def external_database_create(request):
    """Créer une connexion à une base externe"""
    if request.method == 'POST':
        form = ExternalDatabaseForm(request.POST)
        if form.is_valid():
            database = form.save(commit=False)
            database.user = request.user
            database.save()

            # Tester la connexion (TODO: implémenter le test réel)
            try:
                # Placeholder pour test de connexion
                database.status = 'connected'
                database.save()
                messages.success(request, 'Base de données créée avec succès!')
            except Exception as e:
                messages.warning(request, f'Base créée mais erreur: {str(e)}')

            return redirect('database_manager:external_database_detail', pk=database.pk)
    else:
        form = ExternalDatabaseForm()

    return render(request, 'database_manager/external_database_form.html', {'form': form})


@login_required
def external_database_detail(request, pk):
    """Détails d'une base de données externe"""
    database = get_object_or_404(ExternalDatabase, pk=pk, user=request.user)

    context = {
        'database': database,
    }

    return render(request, 'database_manager/external_database_detail.html', context)


@login_required
def external_database_test(request, pk):
    """Tester la connexion à une base externe"""
    database = get_object_or_404(ExternalDatabase, pk=pk, user=request.user)

    try:
        # TODO: Implémenter le test réel de connexion avec SQLAlchemy
        from django.utils import timezone
        database.status = 'connected'
        database.last_connection_test = timezone.now()
        database.save()
        messages.success(request, 'Test de connexion réussi!')
    except Exception as e:
        database.status = 'error'
        database.save()
        messages.error(request, f'Erreur de connexion: {str(e)}')

    return redirect('database_manager:external_database_detail', pk=pk)


@login_required
def schema_list(request):
    """Liste des schémas de base de données"""
    schemas = DatabaseSchema.objects.filter(
        document__user=request.user
    ).order_by('-created_at').select_related('document')

    context = {
        'schemas': schemas,
    }

    return render(request, 'database_manager/schema_list.html', context)


@login_required
def schema_generate(request, document_id):
    """Générer un schéma à partir d'un document"""
    document = get_object_or_404(Document, pk=document_id, user=request.user)

    if document.status != 'completed':
        messages.error(request, 'Le document doit être analysé avant de générer un schéma')
        return redirect('documents:detail', pk=document_id)

    try:
        # Générer le schéma
        generator = SchemaGenerator()
        schema = generator.generate_schema_from_document(document, request.user)

        if schema:
            messages.success(request, 'Schéma généré avec succès!')
            return redirect('database_manager:schema_detail', pk=schema.pk)
        else:
            messages.error(request, 'Impossible de générer le schéma. Vérifiez que le document a été analysé.')
            return redirect('documents:detail', pk=document_id)
    except Exception as e:
        messages.error(request, f'Erreur lors de la génération du schéma: {str(e)}')
        return redirect('documents:detail', pk=document_id)


@login_required
def schema_detail(request, pk):
    """Détails d'un schéma de base de données"""
    schema = get_object_or_404(
        DatabaseSchema,
        pk=pk,
        document__user=request.user
    )

    # Récupérer les tables et leurs champs
    tables = schema.tables.all().prefetch_related('fields')

    # Récupérer les relations pour le diagramme
    relations = schema.relations.all().select_related(
        'from_table', 'to_table', 'from_field', 'to_field'
    )

    context = {
        'schema': schema,
        'tables': tables,
        'relations': relations,
    }

    return render(request, 'database_manager/schema_detail.html', context)


@login_required
def schema_edit(request, pk):
    """Modifier un schéma"""
    schema = get_object_or_404(
        DatabaseSchema,
        pk=pk,
        document__user=request.user
    )

    if request.method == 'POST':
        form = DatabaseSchemaForm(request.POST, instance=schema)
        if form.is_valid():
            form.save()
            schema.status = 'modified'
            schema.save()
            messages.success(request, 'Schéma modifié avec succès!')
            return redirect('database_manager:schema_detail', pk=pk)
    else:
        form = DatabaseSchemaForm(instance=schema)

    context = {
        'form': form,
        'schema': schema,
    }

    return render(request, 'database_manager/schema_form.html', context)


@login_required
def schema_download_sql(request, pk):
    """Télécharger le SQL de création du schéma"""
    schema = get_object_or_404(
        DatabaseSchema,
        pk=pk,
        document__user=request.user
    )

    try:
        # Générer le SQL
        sql_generator = SQLGenerator()
        sql_content = sql_generator.generate_sql_from_schema(schema)

        # Créer la réponse HTTP
        response = HttpResponse(sql_content, content_type='text/plain; charset=utf-8')
        filename = f"schema_{schema.name}_{schema.id}.sql"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        messages.error(request, f'Erreur lors de la génération du SQL: {str(e)}')
        return redirect('database_manager:schema_detail', pk=pk)


@login_required
def schema_validate(request, pk):
    """Valider un schéma"""
    schema = get_object_or_404(
        DatabaseSchema,
        pk=pk,
        document__user=request.user
    )

    if request.method == 'POST':
        form = SchemaValidationForm(request.POST)
        if form.is_valid():
            # Validation simple du schéma
            errors = []
            warnings = []

            # Vérifier qu'il y a au moins une table
            if not schema.tables.exists():
                errors.append("Le schéma doit contenir au moins une table")

            # Vérifier que chaque table a au moins un champ
            for table in schema.tables.all():
                if not table.fields.exists():
                    errors.append(f"La table '{table.name}' n'a aucun champ")

                # Vérifier qu'il y a une clé primaire
                if not table.fields.filter(is_primary_key=True).exists():
                    warnings.append(f"La table '{table.name}' n'a pas de clé primaire")

            if not errors:
                from django.utils import timezone
                schema.status = 'validated'
                schema.validated_by = request.user
                schema.validated_at = timezone.now()
                schema.save()
                messages.success(request, 'Schéma validé avec succès!')
            else:
                for error in errors:
                    messages.error(request, error)

            for warning in warnings:
                messages.warning(request, warning)

            return redirect('database_manager:schema_detail', pk=pk)
    else:
        form = SchemaValidationForm()

    context = {
        'form': form,
        'schema': schema,
    }

    return render(request, 'database_manager/schema_validate.html', context)


@login_required
def table_add(request, schema_id):
    """Ajouter une table à un schéma"""
    schema = get_object_or_404(
        DatabaseSchema,
        pk=schema_id,
        document__user=request.user
    )

    if request.method == 'POST':
        form = DatabaseTableForm(request.POST)
        if form.is_valid():
            table = form.save(commit=False)
            table.schema = schema
            table.save()
            messages.success(request, 'Table ajoutée avec succès!')
            return redirect('database_manager:schema_detail', pk=schema_id)
    else:
        form = DatabaseTableForm()

    context = {
        'form': form,
        'schema': schema,
    }

    return render(request, 'database_manager/table_form.html', context)


@login_required
def field_add(request, table_id):
    """Ajouter un champ à une table"""
    table = get_object_or_404(
        DatabaseTable,
        pk=table_id,
        schema__document__user=request.user
    )

    if request.method == 'POST':
        form = DatabaseFieldForm(request.POST)
        if form.is_valid():
            field = form.save(commit=False)
            field.table = table
            field.save()
            messages.success(request, 'Champ ajouté avec succès!')
            return redirect('database_manager:schema_detail', pk=table.schema.pk)
    else:
        form = DatabaseFieldForm()

    context = {
        'form': form,
        'table': table,
    }

    return render(request, 'database_manager/field_form.html', context)


@login_required
def data_extraction_create(request, schema_id, document_id):
    """
    Lancer une extraction de données d'un document vers un schéma validé
    """
    schema = get_object_or_404(
        DatabaseSchema,
        pk=schema_id,
        document__user=request.user
    )
    document = get_object_or_404(Document, pk=document_id, user=request.user)

    # Vérifier que le schéma est validé
    if schema.status != 'validated':
        messages.error(request, 'Le schéma doit être validé avant de pouvoir extraire des données.')
        return redirect('database_manager:schema_detail', pk=schema_id)

    # Vérifier que le document est analysé
    if document.status != 'completed':
        messages.error(request, 'Le document doit être analysé avant l\'extraction.')
        return redirect('documents:detail', pk=document_id)

    try:
        # Lancer l'extraction
        service = DataExtractionService()
        extraction = service.extract_data_from_document(schema, document)

        messages.success(request, f'Extraction réussie avec un score de confiance de {extraction.confidence_score:.2%}!')
        return redirect('database_manager:data_extraction_detail', pk=extraction.pk)

    except Exception as e:
        messages.error(request, f'Erreur lors de l\'extraction: {str(e)}')
        return redirect('database_manager:schema_detail', pk=schema_id)


@login_required
def data_extraction_list(request):
    """Liste des extractions de données"""
    extractions = DataExtraction.objects.filter(
        schema__document__user=request.user
    ).order_by('-created_at').select_related('schema', 'document', 'validated_by')

    context = {
        'extractions': extractions,
    }

    return render(request, 'database_manager/data_extraction_list.html', context)


@login_required
def data_extraction_detail(request, pk):
    """Détails d'une extraction de données"""
    extraction = get_object_or_404(
        DataExtraction,
        pk=pk,
        schema__document__user=request.user
    )

    # Organiser les données extraites pour l'affichage
    extracted_data = extraction.extracted_data
    tables_data = extracted_data.get('tables', {})

    # Préparer les données pour le template
    tables_info = []
    for table_name, table_info in tables_data.items():
        rows = table_info.get('rows', [])
        tables_info.append({
            'name': table_name,
            'rows': rows,
            'row_count': len(rows),
            'notes': table_info.get('_notes', ''),
            'confidence': table_info.get('_confidence', 0),
        })

    context = {
        'extraction': extraction,
        'tables_info': tables_info,
        'global_notes': extracted_data.get('global_notes', ''),
        'global_confidence': extracted_data.get('global_confidence', 0),
    }

    return render(request, 'database_manager/data_extraction_detail.html', context)


@login_required
def data_extraction_validate(request, pk):
    """Valider une extraction de données"""
    extraction = get_object_or_404(
        DataExtraction,
        pk=pk,
        schema__document__user=request.user
    )

    if request.method == 'POST':
        from django.utils import timezone
        extraction.status = 'validated'
        extraction.validated_by = request.user
        extraction.validated_at = timezone.now()
        extraction.save()

        messages.success(request, 'Extraction validée avec succès!')
        return redirect('database_manager:data_extraction_detail', pk=pk)

    context = {
        'extraction': extraction,
    }

    return render(request, 'database_manager/data_extraction_validate.html', context)


@login_required
def data_extraction_reject(request, pk):
    """Rejeter une extraction de données"""
    extraction = get_object_or_404(
        DataExtraction,
        pk=pk,
        schema__document__user=request.user
    )

    if request.method == 'POST':
        extraction.status = 'rejected'
        extraction.save()

        messages.warning(request, 'Extraction rejetée.')
        return redirect('database_manager:data_extraction_list')

    return redirect('database_manager:data_extraction_detail', pk=pk)


@login_required
def data_extraction_download_sql(request, pk):
    """Télécharger le SQL d'insertion pour une extraction"""
    extraction = get_object_or_404(
        DataExtraction,
        pk=pk,
        schema__document__user=request.user
    )

    try:
        # Générer le SQL
        service = DataExtractionService()
        sql_content = service.generate_insert_sql(extraction)

        # Créer la réponse HTTP
        response = HttpResponse(sql_content, content_type='text/plain')
        filename = f"extraction_{extraction.schema.name}_{extraction.document.id}.sql"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        messages.error(request, f'Erreur lors de la génération du SQL: {str(e)}')
        return redirect('database_manager:data_extraction_detail', pk=pk)


@login_required
def data_extraction_download_json(request, pk):
    """Télécharger le JSON extrait"""
    extraction = get_object_or_404(
        DataExtraction,
        pk=pk,
        schema__document__user=request.user
    )

    import json

    # Créer la réponse HTTP avec le JSON
    json_content = json.dumps(extraction.extracted_data, indent=2, ensure_ascii=False)
    response = HttpResponse(json_content, content_type='application/json')
    filename = f"extraction_{extraction.schema.name}_{extraction.document.id}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response
