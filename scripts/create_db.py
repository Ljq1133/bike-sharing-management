"""Create DB tables using app.db and SQLAlchemy models.
Usage:
  # ensure env DATABASE_URL is set, e.g.: 
  # $env:DATABASE_URL = "postgresql://bike:secret@localhost:5432/bikedb"
  python scripts/create_db.py
"""
import os
import sys

# add project root to path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db import engine, Base
import app.models as models

print('Using database:', engine.url.render_as_string(hide_password=True))
print('Creating tables...')
Base.metadata.create_all(bind=engine)
print('Done')
