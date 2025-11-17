# FICHIER: docmind_project/urls.py
# CONFIGURATION DES URLs PRINCIPALES
# ============================================

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('documents/', include('documents.urls')),
    path('chat/', include('chat.urls')),
    path('database/', include('database_manager.urls')),
    path('landing/', include('core.urls')),  # Keep landing available at /landing/
]

# Servir les fichiers media en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
