from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),  # Root URL now uses home view (redirects to login or dashboard)
    path('landing/', views.landing_page, name='landing'),  # Landing page moved to /landing/
    path('document-actions/', views.document_actions, name='document_actions'),
    path('upload-source/', views.upload_source, name='upload_source'),

    path('dashboard/', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('settings/', views.settings, name='settings'),
]