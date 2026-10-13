"""Seed the database with N random bikes within max_radius_km of a center point.
Usage:
  # ensure env DATABASE_URL is set
  .\.venv\Scripts\python.exe scripts\seed_bikes.py --count 100 --max-radius 50
"""
import random, math, os
from sqlalchemy.orm import Session

# add project root to path
import sys
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db import SessionLocal
import app.models as models


def random_point_around(lat, lon, max_km):
    # pick random distance (0..max_km) and bearing
    d = random.random() * max_km
    bearing = random.random() * 2 * math.pi
    R = 6371.0
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.asin(math.sin(lat1) * math.cos(d/R) + math.cos(lat1) * math.sin(d/R) * math.cos(bearing))
    lon2 = lon1 + math.atan2(math.sin(bearing) * math.sin(d/R) * math.cos(lat1), math.cos(d/R) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


def main(count=100, max_radius_km=50, center_lat=31.23, center_lng=121.47):
    db: Session = SessionLocal()
    created = 0
    try:
        for i in range(count):
            lat, lng = random_point_around(center_lat, center_lng, max_radius_km)
            b = models.Bike(lat=lat, lng=lng, status=models.BikeStatus.available, usage_count=0, rating=5.0)
            db.add(b)
            created += 1
        db.commit()
    except Exception as e:
        db.rollback()
        print('Error:', e)
    finally:
        db.close()
    print(f'Created {created} bikes (center {center_lat},{center_lng}, max_radius_km={max_radius_km})')


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--count', type=int, default=100)
    p.add_argument('--max-radius', type=float, default=50.0)
    p.add_argument('--center-lat', type=float, default=31.23)
    p.add_argument('--center-lng', type=float, default=121.47)
    args = p.parse_args()
    main(count=args.count, max_radius_km=args.max_radius, center_lat=args.center_lat, center_lng=args.center_lng)
