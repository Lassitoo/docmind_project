# 🧠 DocMind - Système d'Analyse Documentaire Intelligente

DocMind est une plateforme d'IA documentaire évolutive qui permet d'analyser des documents, de répondre aux questions des utilisateurs et de générer automatiquement des structures de base de données adaptées.

## 🎯 Fonctionnalités Principales

### 1. **Upload et Analyse de Documents**
- Upload de documents (PDF, Word, TXT)
- Extraction automatique du contenu
- Analyse NLP pour identifier:
  - Entités nommées
  - Mots-clés
  - Structure du document
  - Résumé automatique

### 2. **Chat Intelligent (Q&A)**
- Conversations basées sur le contenu des documents
- Réponses contextualisées avec références aux sources
- Historique des conversations
- Support multi-documents

### 3. **Génération de Schémas de Base de Données**
- Génération automatique de structures de BDD à partir des documents
- Interface visuelle pour modifier et valider les schémas
- Export SQL
- Gestion des tables, champs et relations

### 4. **Connexion aux Bases Externes**
- Connexion à des bases de données existantes (PostgreSQL, MySQL, etc.)
- Importation de schémas existants
- Requêtes combinées (documents + BDD externe)

## 🚀 Installation

### Prérequis
- Python 3.10+
- pip
- virtualenv (recommandé)

### Étapes d'installation

1. **Cloner le projet**
```bash
cd C:/Users/yayab/PycharmProjects/Pharmacie/docmind_project
```

2. **Créer un environnement virtuel**
```bash
python -m venv venv
venv\Scripts\activate  # Sur Windows
# source venv/bin/activate  # Sur Linux/Mac
```

3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

4. **Configuration**
Créez un fichier `.env` à la racine du projet:
```env
SECRET_KEY=votre-clé-secrète-django
DEBUG=True
OPENAI_API_KEY=votre-clé-api-openai  # Optionnel
```

5. **Migrations de base de données**
```bash
python manage.py makemigrations
python manage.py migrate
```

6. **Créer un super-utilisateur**
```bash
python manage.py createsuperuser
```

7. **Créer les dossiers pour fichiers statiques et media**
```bash
mkdir static
mkdir media
```

8. **Lancer le serveur de développement**
```bash
python manage.py runserver
```

Accédez à l'application sur `http://localhost:8000`

## 📁 Structure du Projet

```
docmind_project/
├── core/                   # App principale (dashboard, profils)
│   ├── models.py          # UserProfile, ActivityLog, SystemSettings
│   ├── views.py
│   ├── forms.py
│   └── urls.py
├── documents/             # Gestion des documents
│   ├── models.py         # Document, DocumentContent, DocumentAnalysis
│   ├── views.py
│   ├── forms.py
│   ├── services.py       # Services d'analyse et traitement
│   └── urls.py
├── chat/                  # Chat et conversations
│   ├── models.py         # Conversation, Message, QueryContext
│   ├── views.py
│   ├── forms.py
│   ├── services.py       # Services de génération de réponses
│   └── urls.py
├── database_manager/      # Gestion des schémas et BDD externes
│   ├── models.py         # DatabaseSchema, ExternalDatabase, etc.
│   ├── views.py
│   ├── forms.py
│   ├── services.py       # Services de génération de schémas
│   └── urls.py
├── templates/             # Templates HTML
│   ├── base.html
│   ├── core/
│   ├── documents/
│   ├── chat/
│   └── database_manager/
├── static/               # Fichiers statiques
│   ├── css/
│   └── js/
├── media/                # Fichiers uploadés
├── docmind_project/      # Configuration Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── requirements.txt       # Dépendances Python
└── manage.py
```

## 🔧 Configuration

### Apps Django
- `core`: Gestion des utilisateurs et dashboard
- `documents`: Upload et analyse de documents
- `chat`: Conversations et Q&A
- `database_manager`: Génération de schémas et connexion BDD

### Technologies Utilisées
- **Backend**: Django 5.2
- **Frontend**: Bootstrap 5, jQuery
- **Traitement de documents**: PyPDF2, python-docx
- **IA/NLP**: OpenAI API (optionnel)
- **Base de données**: SQLite (dev), PostgreSQL (prod recommandé)

## 📝 Utilisation

### 1. Upload d'un Document
1. Allez dans "Documents" > "Nouveau document"
2. Sélectionnez votre fichier (PDF, DOCX, TXT)
3. Le système analyse automatiquement le document

### 2. Créer une Conversation
1. Allez dans "Conversations" > "Nouvelle conversation"
2. Sélectionnez les documents à utiliser
3. Posez vos questions

### 3. Générer un Schéma de Base de Données
1. Ouvrez un document analysé
2. Cliquez sur "Générer un schéma"
3. Modifiez et validez le schéma proposé

### 4. Connecter une Base Externe
1. Allez dans "Bases de données" > "Nouvelle connexion"
2. Entrez les informations de connexion
3. Testez la connexion

## 🔐 Sécurité

**Important pour la production:**
- Changez la `SECRET_KEY` dans settings.py
- Définissez `DEBUG = False`
- Configurez `ALLOWED_HOSTS`
- Chiffrez les mots de passe de BDD externes
- Utilisez HTTPS
- Configurez les CORS si nécessaire

## 📊 Administration

Accédez à l'interface d'administration Django sur `/admin/`

Fonctionnalités disponibles:
- Gestion des utilisateurs et profils
- Modération des documents
- Supervision des conversations
- Validation des schémas
- Logs d'activité

## 🧪 Tests

```bash
# Lancer les tests
pytest

# Avec coverage
pytest --cov=.
```

## 🚀 Déploiement en Production

### Avec Gunicorn
```bash
gunicorn docmind_project.wsgi:application --bind 0.0.0.0:8000
```

### Variables d'environnement recommandées
```env
DEBUG=False
SECRET_KEY=votre-clé-secrète-très-longue
ALLOWED_HOSTS=votre-domaine.com
DATABASE_URL=postgres://user:pass@host:port/dbname
OPENAI_API_KEY=sk-...
```

## 📄 Licence

Ce projet est sous licence MIT.

## 👥 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## 📞 Support

Pour toute question ou problème, contactez l'équipe de développement.

---

**Développé avec ❤️ pour l'analyse documentaire intelligente**
