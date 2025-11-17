import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'docmind_project.settings')
django.setup()

from django.contrib.auth.models import User
u = User.objects.get(username='testuser')
u.set_password('password123')
u.save()
print('Password set for testuser')