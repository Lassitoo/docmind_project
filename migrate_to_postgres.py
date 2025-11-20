#!/usr/bin/env python
"""
Script de migration de SQLite vers PostgreSQL pour Django
"""
import os
import sys
import django
from pathlib import Path

# Configuration Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'docmind_project.settings')
django.setup()

from django.core.management import execute_from_command_line
from django.db import connection
import sqlite3
import psycopg2
from psycopg2.extras import execute_values

def migrate_sqlite_to_postgres():
    """
    Migre les données de SQLite vers PostgreSQL
    """
    # Configuration des bases de données
    SQLITE_DB = BASE_DIR / 'db.sqlite3'
    POSTGRES_CONFIG = {
        'host': 'localhost',
        'database': 'docmind_db',
        'user': 'postgres',
        'password': 'lassito',
        'port': 5432
    }

    print("🔄 Début de la migration SQLite → PostgreSQL")

    try:
        # Connexion SQLite
        sqlite_conn = sqlite3.connect(str(SQLITE_DB))
        sqlite_cursor = sqlite_conn.cursor()

        # Connexion PostgreSQL
        pg_conn = psycopg2.connect(**POSTGRES_CONFIG)
        pg_cursor = pg_conn.cursor()

        # Obtenir toutes les tables
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in sqlite_cursor.fetchall()]

        print(f"📋 Tables trouvées: {tables}")

        for table in tables:
            print(f"🔄 Migration de la table: {table}")

            # Obtenir la structure de la table
            sqlite_cursor.execute(f"PRAGMA table_info({table})")
            columns = sqlite_cursor.fetchall()
            column_names = [col[1] for col in columns]

            # Obtenir les données
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()

            if not rows:
                print(f"⚠️  Table {table} vide, ignorée")
                continue

            # Préparer l'insertion PostgreSQL
            placeholders = ','.join(['%s'] * len(column_names))
            insert_query = f"INSERT INTO {table} ({','.join(column_names)}) VALUES ({placeholders})"

            # Insérer les données par lots
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                try:
                    execute_values(pg_cursor, insert_query, batch)
                    pg_conn.commit()
                    print(f"✅ Lot {i//batch_size + 1} inséré ({len(batch)} lignes)")
                except Exception as e:
                    print(f"❌ Erreur lors de l'insertion du lot {i//batch_size + 1}: {e}")
                    pg_conn.rollback()
                    continue

            print(f"✅ Table {table} migrée ({len(rows)} lignes)")

        print("🎉 Migration terminée avec succès!")

    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        raise
    finally:
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
        if 'pg_conn' in locals():
            pg_conn.close()

if __name__ == '__main__':
    migrate_sqlite_to_postgres()