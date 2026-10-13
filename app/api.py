from fastapi import APIRouter, Depends, HTTPException, status
import os
from sqlalchemy.orm import Session
from . import schemas, crud, models
from .db import get_db
from .security import create_access_token
from .auth import get_current_user, oauth2_scheme
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter()


@router.post("/api/users", response_model=schemas.UserOut)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="username already exists")
    # If user requests maintainer role, require invite code match
    if getattr(user_in, 'is_maintainer', False):
        invite = getattr(user_in, 'invite_code', None)
        secret = os.getenv('MAINTAINER_INVITE', '')
        if not secret or invite != secret:
            raise HTTPException(status_code=403, detail="invalid or missing invite code for maintainer registration")
    user = crud.create_user(db, user_in)
    return user


@router.post("/api/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/api/bikes/nearby", response_model=list[schemas.BikeOut])
def get_bikes_nearby(lat: float, lng: float, radius_km: float = 1.0, db: Session = Depends(get_db)):
    bikes = crud.list_bikes_nearby(db, lat, lng, radius_km)
    return bikes


@router.post("/api/bikes", response_model=schemas.BikeOut)
def create_bike(lat: float, lng: float, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # any authenticated user may create bikes for demo
    b = crud.create_bike(db, lat, lng)
    return b


@router.post("/api/rentals", status_code=201)
def rent_bike(bike_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rental = crud.rent_bike(db, user.id, bike_id)
    if not rental:
        raise HTTPException(status_code=400, detail="bike not available")
    return {"rental_id": rental.id}


@router.post("/api/rentals/{rental_id}/return")
def return_bike(rental_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rental = db.query(models.Rental).filter(models.Rental.id == rental_id, models.Rental.user_id == user.id).first()
    if not rental:
        raise HTTPException(status_code=404, detail="rental not found")
    res = crud.return_bike(db, rental_id)
    if not res:
        raise HTTPException(status_code=400, detail="cannot return")
    return {"ok": True}


@router.post("/api/bikes/{bike_id}/status")
def set_bike_status(bike_id: int, status: models.BikeStatus, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user.is_maintainer:
        raise HTTPException(status_code=403, detail="maintainer only")
    bike = crud.set_bike_status(db, bike_id, status)
    if not bike:
        raise HTTPException(status_code=404, detail="bike not found")
    return {"ok": True}


@router.get("/api/me", response_model=schemas.UserOut)
def me(user=Depends(get_current_user)):
    return user
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app import crud, schemas
from app.db import get_db
from app.security import hash_password
from app.auth import create_access_token, get_current_user, oauth2_scheme
from fastapi import Depends
from datetime import timedelta
from app.core.config import settings
from app import models

router = APIRouter()


@router.post('/users', response_model=schemas.UserOut, status_code=201)
def create_user(user_in: schemas.UserCreate, db: Session = Depends(get_db), response: Response = None):
    # check existing username and provide friendly error
    if crud.get_user_by_username(db, username=user_in.username):
        raise HTTPException(status_code=409, detail="Username already exists")

    # hash password (security.hash_password uses passlib with bcrypt_sha256)
    try:
        pw_hash = hash_password(user_in.password)
    except ValueError as e:
        # passlib may raise ValueError for invalid inputs; map to 400
        raise HTTPException(status_code=400, detail=str(e))

    try:
        user = crud.create_user(db=db, username=user_in.username, password_hash=pw_hash, contact=user_in.contact, is_maintainer=bool(user_in.is_maintainer))
    except crud.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        # map common DB integrity errors to 409, otherwise rethrow (will become 500)
        from sqlalchemy.exc import IntegrityError
        if isinstance(e, IntegrityError):
            raise HTTPException(status_code=409, detail="User could not be created (integrity error)")
        raise
    # Ensure the response status code is set to 201 and return model
    if response is not None:
        response.status_code = 201
    return user

@router.get('/bikes', response_model=list[schemas.BikeOut])
def get_bikes(limit: int = 100, db: Session = Depends(get_db)):
    return crud.list_bikes(db=db, limit=limit)


@router.get('/bikes/nearby', response_model=list[schemas.BikeOut])
def get_bikes_nearby(lat: float, lon: float, radius_km: float = 0.5, limit: int = 50, db: Session = Depends(get_db)):
    """Query nearby bikes by latitude/longitude (km). Returns bikes sorted by distance."""
    bikes = crud.list_bikes_nearby(db=db, latitude=lat, longitude=lon, radius_km=radius_km, limit=limit)
    return bikes

@router.post('/bikes', response_model=schemas.BikeOut)
def post_bike(bike_in: schemas.BikeCreate, db: Session = Depends(get_db)):
    bike = crud.create_bike(db=db, bike_in=bike_in)
    return bike



@router.post('/bikes/{bike_id}/status', response_model=schemas.BikeOut)
def post_bike_status(bike_id: int, payload: dict, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Modify bike status. Payload example: {"status": "maintenance"}.

    Requires maintainer role (JWT)."""
    # validate token and maintainer role
    user = get_current_user(token=token, db=db)
    if not getattr(user, 'is_maintainer', False):
        raise HTTPException(status_code=403, detail="Maintainer role required")
    status = payload.get('status')
    if not status:
        raise HTTPException(status_code=400, detail="Missing status")
    try:
        bike = crud.set_bike_status(db=db, bike_id=bike_id, status=status)
    except crud.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except crud.BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
    return bike

@router.post('/rentals', response_model=schemas.RentalOut)
def start_rental(r_in: schemas.RentalCreate, db: Session = Depends(get_db)):
    try:
        rental = crud.rent_bike(db=db, user_id=r_in.user_id, bike_id=r_in.bike_id)
    except crud.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except crud.BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
    return rental

@router.post('/rentals/{rental_id}/return', response_model=schemas.RentalOut)
def end_rental(rental_id: int, fee: float = 0.0, db: Session = Depends(get_db)):
    try:
        rental = crud.return_bike(db=db, rental_id=rental_id, fee=fee)
    except crud.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except crud.BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
    return rental


@router.post('/auth/login', response_model=schemas.Token)
def login_for_access_token(form_data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = crud.authenticate_user(db=db, username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(data={"user_id": user.user_id}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


def _current_user_dep(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    return get_current_user(token=token, db=db)



@router.get('/me', response_model=schemas.UserOut)
def read_current_user(current_user: models.User = Depends(_current_user_dep)):
    return current_user
