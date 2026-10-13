from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from sqlalchemy import func
import math

from . import models, schemas
from .security import verify_password


def create_user(db: Session, username: str, password_hash: str, is_maintainer: bool = False):
    """Create a new user. Uses model fields defined in `app.models.User` (username, hashed_password, is_maintainer)."""
    user = models.User(username=username, hashed_password=password_hash, is_maintainer=bool(is_maintainer))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username=username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def list_bikes_nearby(db: Session, lat: float, lng: float, radius_km: float = 1.0):
    bikes = db.query(models.Bike).all()
    out = []
    for b in bikes:
        try:
            d = haversine(lat, lng, float(b.lat), float(b.lng))
        except Exception:
            continue
        if d <= radius_km:
            out.append(b)
    return out


def list_bikes(db: Session, limit: int = 100):
    """Return up to `limit` bikes (no location filtering)."""
    return db.query(models.Bike).limit(limit).all()


def create_bike(db: Session, bike_in: schemas.BikeCreate):
    # support both latitude/longitude and lat/lng naming
    lat = getattr(bike_in, 'latitude', None) or getattr(bike_in, 'lat', None)
    lng = getattr(bike_in, 'longitude', None) or getattr(bike_in, 'lng', None)
    bike = models.Bike(lat=lat or 0.0, lng=lng or 0.0)
    db.add(bike)
    db.commit()
    db.refresh(bike)
    return bike


def rent_bike(db: Session, user_id: int, bike_id: int):
    bike = db.query(models.Bike).with_for_update().filter(models.Bike.id == bike_id).first()
    if not bike:
        raise Exception('Bike not found')
    # Ensure a user does not have more than one ongoing rental
    existing = db.query(models.Rental).filter(models.Rental.user_id == user_id, models.Rental.status == models.RentalStatus.ongoing).first()
    if existing:
        raise Exception('User already has an ongoing rental')
    # Only available bikes can be rented
    if bike.status != models.BikeStatus.available:
        raise Exception('Bike not available for rent')
    bike.status = models.BikeStatus.in_use
    rental = models.Rental(user_id=user_id, bike_id=bike_id, start_time=datetime.utcnow(), status=models.RentalStatus.ongoing)
    db.add(rental)
    db.commit()
    db.refresh(rental)
    return rental


def return_bike(db: Session, rental_id: int):
    return return_bike_with_rating(db, rental_id, rating=None)


def return_bike_with_rating(db: Session, rental_id: int, rating: int | None = None):
    rental = db.query(models.Rental).filter(models.Rental.id == rental_id).first()
    if not rental or rental.status != models.RentalStatus.ongoing:
        return None
    bike = db.query(models.Bike).filter(models.Bike.id == rental.bike_id).first()
    rental.status = models.RentalStatus.returned
    rental.end_time = datetime.utcnow()
    if rating is not None:
        try:
            rental.rating = int(rating)
        except Exception:
            rental.rating = None
    if bike:
        bike.status = models.BikeStatus.available
        # increment usage count on return
        try:
            bike.usage_count = (bike.usage_count or 0) + 1
        except Exception:
            bike.usage_count = 1
        # recalc average rating from rentals that have a rating
        # flush pending changes so the just-set rental.rating is visible to the aggregate query
        try:
            db.flush()
        except Exception:
            pass
        avg = db.query(func.avg(models.Rental.rating)).filter(models.Rental.bike_id == bike.id, models.Rental.rating != None).scalar()
        try:
            bike.rating = float(avg) if avg is not None else 0.0
        except Exception:
            bike.rating = 0.0
    db.commit()
    db.refresh(rental)
    if bike:
        db.refresh(bike)
    return rental


def set_bike_status(db: Session, bike_id: int, status: str, maintainer_id: int | None = None):
    bike = db.query(models.Bike).filter(models.Bike.id == bike_id).first()
    if not bike:
        return None
    try:
        enum_val = models.BikeStatus(status)
    except Exception:
        try:
            enum_val = getattr(models.BikeStatus, status)
        except Exception:
            return None
    # Prevent setting maintenance on a bike that's currently rented
    if enum_val == models.BikeStatus.maintenance and bike.status == models.BikeStatus.in_use:
        raise Exception('Cannot set maintenance while bike is rented')
    # Prevent arbitrary setting to in_use via this endpoint
    if enum_val == models.BikeStatus.in_use:
        raise Exception('Cannot set bike to in_use via maintenance endpoint')
    # handle maintenance records and reset logic
    prev_status = bike.status
    bike.status = enum_val
    # if switching to maintenance: create a maintenance record (record maintainer if provided)
    if enum_val == models.BikeStatus.maintenance and prev_status != models.BikeStatus.maintenance:
        try:
            m = models.Maintenance(bike_id=bike.id, maintainer_id=maintainer_id)
            db.add(m)
        except Exception:
            pass
    # if switching from maintenance -> available: mark maintenance end and reset score/usage
    if prev_status == models.BikeStatus.maintenance and enum_val == models.BikeStatus.available:
        try:
            # find latest open maintenance record for this bike
            m = db.query(models.Maintenance).filter(models.Maintenance.bike_id == bike.id, models.Maintenance.end_time == None).order_by(models.Maintenance.start_time.desc()).first()
            if m:
                from datetime import datetime as _dt
                m.end_time = _dt.utcnow()
        except Exception:
            pass
        # reset rating (score) to default 5 and usage_count to 0
        bike.rating = 5.0
        bike.usage_count = 0
    db.commit()
    db.refresh(bike)
    return bike


def delete_bike(db: Session, bike_id: int):
    bike = db.query(models.Bike).filter(models.Bike.id == bike_id).first()
    if not bike:
        return None
    # Remove any rentals referencing this bike first to avoid FK constraint errors.
    # This will remove both historical and ongoing rentals for the bike.
    db.query(models.Rental).filter(models.Rental.bike_id == bike_id).delete(synchronize_session=False)
    db.delete(bike)
    db.commit()
    return True


def get_user_rentals(db: Session, user_id: int):
    return db.query(models.Rental).filter(models.Rental.user_id == user_id).order_by(models.Rental.start_time.desc()).all()


def list_maintenances(db: Session, limit: int = 200):
    return db.query(models.Maintenance).order_by(models.Maintenance.start_time.desc()).limit(limit).all()


def set_user_jti(db: Session, user_id: int, jti: str):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    user.active_jti = jti
    db.commit()
    db.refresh(user)
    return user


def clear_user_jti(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    user.active_jti = None
    db.commit()
    db.refresh(user)
    return user
