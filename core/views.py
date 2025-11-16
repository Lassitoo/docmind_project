# FICHIER: core/views.py
# VUES PRINCIPALES DE L'APPLICATION
# ============================================

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.db.models import Count, Sum
from documents.models import Document
from chat.models import Conversation
from database_manager.models import ExternalDatabase, DatabaseSchema
from .forms import UserRegistrationForm, UserProfileForm, UserUpdateForm
from django.shortcuts import render, redirect
from django.contrib import messages
from documents.models import Document
from chat.models import Conversation
import zipfile
import os
from django.conf import settings

def home(request):
    """Page d'accueil"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return render(request, 'core/home.html')


@login_required
def dashboard(request):
    """Tableau de bord principal"""
    user = request.user

    # Statistiques
    total_documents = Document.objects.filter(user=user).count()
    completed_documents = Document.objects.filter(user=user, status='completed').count()
    total_conversations = Conversation.objects.filter(user=user).count()
    total_schemas = DatabaseSchema.objects.filter(document__user=user).count()

    # Stockage
    storage_used = user.profile.get_used_storage_mb() if hasattr(user, 'profile') else 0
    storage_limit = user.profile.max_storage_mb if hasattr(user, 'profile') else 1000
    storage_percentage = (storage_used / storage_limit * 100) if storage_limit > 0 else 0

    # Documents récents
    recent_documents = Document.objects.filter(user=user).order_by('-uploaded_at')[:5]

    # Conversations récentes
    recent_conversations = Conversation.objects.filter(user=user).order_by('-updated_at')[:5]

    # Schémas récents
    recent_schemas = DatabaseSchema.objects.filter(
        document__user=user
    ).order_by('-created_at')[:5]

    context = {
        'total_documents': total_documents,
        'completed_documents': completed_documents,
        'total_conversations': total_conversations,
        'total_schemas': total_schemas,
        'storage_used': round(storage_used, 2),
        'storage_limit': storage_limit,
        'storage_percentage': round(storage_percentage, 2),
        'recent_documents': recent_documents,
        'recent_conversations': recent_conversations,
        'recent_schemas': recent_schemas,
    }

    return render(request, 'core/dashboard.html', context)


def register(request):
    """Inscription d'un nouvel utilisateur"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Votre compte a été créé avec succès!')
            return redirect('core:dashboard')
    else:
        form = UserRegistrationForm()

    return render(request, 'core/register.html', {'form': form})


@login_required
def profile(request):
    """Page de profil utilisateur"""
    user = request.user

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=user.profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Votre profil a été mis à jour!')
            return redirect('core:profile')
    else:
        user_form = UserUpdateForm(instance=user)
        profile_form = UserProfileForm(instance=user.profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }

    return render(request, 'core/profile.html', context)


@login_required
def settings(request):
    """Page des paramètres"""
    return render(request, 'core/settings.html')


def logout_view(request):
    """Déconnexion"""
    logout(request)
    messages.info(request, 'Vous avez été déconnecté.')
    return redirect('core:home')

def landing_page(request):
    """Prismate.AI landing page"""
    return render(request, 'core/landing.html')

def document_actions(request):
    """Document actions page with upload interface"""
    return render(request, 'core/document_actions.html')

from django.shortcuts import render, redirect
from django.contrib import messages
from documents.models import Document, DocumentContent
from chat.models import Conversation
import os
import zipfile

def upload_source(request):
    """Handle PDF/ZIP file upload with PROPER processing"""
    if request.method == 'POST':
        files = request.FILES.getlist('files')
        agent_type = request.POST.get('agent_type', 'modeler')
        
        if not files:
            messages.error(request, 'Aucun fichier sélectionné')
            return redirect('core:document_actions')
        
        uploaded_documents = []
        
        for file in files:
            if file.name.endswith('.pdf'):
                # Create document
                document = Document.objects.create(
                    title=file.name,
                    file=file,
                    user=request.user if request.user.is_authenticated else None,
                    status='processing'
                )
                
                # EXTRACT CONTENT using PDFStructureExtractor
                from chat.pdf_extractor import PDFStructureExtractor
                try:
                    pdf_path = document.file.path
                    
                    # Extract full structure
                    structure = PDFStructureExtractor.extract_structure(pdf_path)
                    
                    if structure['success']:
                        # Extract text with structure preserved
                        full_text = PDFStructureExtractor.extract_text_with_structure(pdf_path)
                        
                        # Create DocumentContent (THIS IS THE FIX!)
                        DocumentContent.objects.create(
                            document=document,
                            raw_text=full_text,  # ← Save to raw_text
                            processed_text=full_text,
                            page_count=structure['total_pages'],
                            pdf_structure=structure  # Save full structure too
                        )
                        
                        document.status = 'completed'
                        document.save()
                        
                        print(f"✅ Document {document.id} ({document.title}) processed:")
                        print(f"   - Pages: {structure['total_pages']}")
                        print(f"   - Text extracted: {len(full_text)} characters")
                        print(f"   - Tables found: {PDFStructureExtractor.get_tables_count(pdf_path)}")
                    else:
                        print(f"❌ Failed to extract from document {document.id}: {structure.get('error')}")
                        document.status = 'error'
                        document.save()
                    
                except Exception as e:
                    print(f"❌ Error processing document {document.id}: {e}")
                    import traceback
                    traceback.print_exc()
                    document.status = 'error'
                    document.save()
                
                uploaded_documents.append(document)
                
            elif file.name.endswith('.zip'):
                # Extract PDFs from ZIP
                zip_path = os.path.join(settings.MEDIA_ROOT, 'temp_' + file.name)
                
                with open(zip_path, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
                
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        for zip_info in zip_ref.filelist:
                            if zip_info.filename.endswith('.pdf'):
                                pdf_content = zip_ref.read(zip_info.filename)
                                pdf_name = os.path.basename(zip_info.filename)
                                
                                pdf_path = os.path.join(settings.MEDIA_ROOT, 'documents', pdf_name)
                                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                                
                                with open(pdf_path, 'wb') as pdf_file:
                                    pdf_file.write(pdf_content)
                                
                                document = Document.objects.create(
                                    title=pdf_name,
                                    file='documents/' + pdf_name,
                                    user=request.user if request.user.is_authenticated else None,
                                    status='processing'
                                )
                                
                                from chat.pdf_extractor import PDFStructureExtractor
                                try:
                                    structure = PDFStructureExtractor.extract_structure(pdf_path)
                                    
                                    if structure['success']:
                                        full_text = PDFStructureExtractor.extract_text_with_structure(pdf_path)
                                        
                                        DocumentContent.objects.create(
                                            document=document,
                                            raw_text=full_text,
                                            processed_text=full_text,
                                            page_count=structure['total_pages'],
                                            pdf_structure=structure
                                        )
                                        
                                        document.status = 'completed'
                                        document.save()
                                        print(f"✅ ZIP Document {document.id} processed")
                                    else:
                                        document.status = 'error'
                                        document.save()
                                        
                                except Exception as e:
                                    print(f"❌ Error processing ZIP document: {e}")
                                    document.status = 'error'
                                    document.save()
                                
                                uploaded_documents.append(document)
                finally:
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
        
        if not uploaded_documents:
            messages.error(request, 'Aucun fichier PDF trouvé')
            return redirect('core:document_actions')
        
        # Create conversation and redirect
        if agent_type == 'modeler':
            conversation = Conversation.objects.create(
                user=request.user if request.user.is_authenticated else None,
                title=f"Analyse - {uploaded_documents[0].title}",
                use_documents=True
            )
            conversation.documents.set(uploaded_documents)
            
            messages.success(request, f'{len(uploaded_documents)} document(s) traité(s) avec succès!')
            return redirect('chat:conversation_detail', pk=conversation.pk)
        
        elif agent_type == 'validation':
            messages.info(request, 'Agent Validation - Fonctionnalité à venir')
            return redirect('documents:list')
        
        elif agent_type == 'transformation':
            messages.info(request, 'Agent Transformation - Fonctionnalité à venir')
            return redirect('documents:list')
    
    return redirect('core:document_actions')

