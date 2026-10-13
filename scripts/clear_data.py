"""Clear all bikes, maintenances and rentals from the configured database.
Usage:
  .\.venv\Scripts\python.exe scripts\clear_data.py
Ensure `DATABASE_URL` env is set (same as used for the app).
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db import SessionLocal
import app.models as models

def main():
    db = SessionLocal()
    try:
        r = db.query(models.Rental).delete(synchronize_session=False)
        m = db.query(models.Maintenance).delete(synchronize_session=False)
        b = db.query(models.Bike).delete(synchronize_session=False)
        db.commit()
        print(f"Deleted rentals={r}, maintenances={m}, bikes={b}")
    except Exception as e:
        db.rollback()
        print('Error clearing data:', e)
    finally:
        db.close()

if __name__ == '__main__':
    main()
