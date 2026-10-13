
from fastapi import FastAPI, Depends, HTTPException, status, Body, Request
from typing import Optional
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os

from .db import engine, Base, get_db
from . import crud, models, schemas
from .security import create_access_token, verify_password, get_password_hash
import uuid

app = FastAPI()

# create tables
Base.metadata.create_all(bind=engine)
# ensure new columns (like users.active_jti) exist when models changed
from .db import ensure_active_jti_column
try:
    ensure_active_jti_column()
except Exception:
    pass

# mount static
app.mount("/static", StaticFiles(directory="app/static"), name="static")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from jose import jwt, JWTError
    from .security import SECRET_KEY, ALGORITHM
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        token_jti = payload.get('jti')
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # enforce single active session: token jti must match user's stored active_jti (if set)
    if getattr(user, 'active_jti', None) and token_jti != user.active_jti:
        raise HTTPException(status_code=401, detail='Token revoked (another session active)')
    return user


@app.post('/api/users', response_model=schemas.UserOut)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # validate
    if not user_in.username or not user_in.password:
        raise HTTPException(status_code=400, detail="username/password required")
    if crud.get_user_by_username(db, username=user_in.username):
        raise HTTPException(status_code=409, detail="username exists")
    if len(user_in.password) <= 8 or not any(c.isalpha() for c in user_in.password) or not any(c.isdigit() for c in user_in.password):
        raise HTTPException(status_code=400, detail='password must be >8 characters and include letters and digits')
    # maintainer invite check
    if getattr(user_in, 'is_maintainer', False):
        secret = os.getenv('MAINTAINER_INVITE','')
        if not secret or getattr(user_in, 'invite_code', None) != secret:
            raise HTTPException(status_code=403, detail='invalid or missing invite code')
    # create hashed password and call CRUD layer which expects a password_hash
    hashed = get_password_hash(user_in.password)
    user = crud.create_user(db, username=user_in.username, password_hash=hashed, is_maintainer=bool(getattr(user_in, 'is_maintainer', False)))
    return user


@app.post('/api/auth/login')
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail='Invalid credentials')
    # create token with jti and persist jti to enforce single active session
    # allow new login to overwrite any previous active_jti (so closing browser doesn't block re-login)
    jti = uuid.uuid4().hex
    token = create_access_token({'sub': user.username, 'jti': jti}, jti=jti)
    crud.set_user_jti(db, user.id, jti)
    return {"access_token": token, "token_type": "bearer"}


@app.get('/api/me', response_model=schemas.UserOut)
def me(user = Depends(get_current_user)):
    return user


@app.post('/api/auth/logout')
def logout(user = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        crud.clear_user_jti(db, user.id)
    except Exception:
        pass
    return {'status':'ok'}


@app.get('/api/bikes/nearby', response_model=list[schemas.BikeOut])
def bikes_nearby(lat: float, lng: float, radius_km: float = 1.0, db: Session = Depends(get_db)):
    bikes = crud.list_bikes_nearby(db, lat, lng, radius_km)
    return bikes


@app.get('/api/bikes', response_model=list[schemas.BikeOut])
def bikes_all(request: Request, db: Session = Depends(get_db)):
    """Return bikes visible to the caller.

    - Maintainers: see all bikes
    - Anonymous or normal users: see only `available` bikes
    - Authenticated normal user: additionally see bikes they currently have an ongoing rental for
    """
    # try resolve current user from Authorization header (optional)
    user = None
    auth = request.headers.get('authorization')
    if auth and auth.lower().startswith('bearer '):
        token = auth.split(' ', 1)[1]
        try:
            user = get_current_user(token, db)
        except Exception:
            user = None

    bikes = crud.list_bikes(db)
    # maintainers see all
    if user and getattr(user, 'is_maintainer', False):
        return bikes

    out = []
    for b in bikes:
        # always include available
        if b.status == models.BikeStatus.available:
            out.append(b)
            continue
        # include in_use only if the current user is the renter
        if b.status == models.BikeStatus.in_use and user:
            own_rental = db.query(models.Rental).filter(models.Rental.bike_id == b.id, models.Rental.user_id == user.id, models.Rental.status == models.RentalStatus.ongoing).first()
            if own_rental:
                out.append(b)
    return out


@app.post('/api/bikes', response_model=schemas.BikeOut)
def post_bike(bike_in: schemas.BikeCreate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    bike = crud.create_bike(db, bike_in)
    return bike


@app.delete('/api/bikes/{bike_id}')
def delete_bike(bike_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    if not getattr(user, 'is_maintainer', False):
        raise HTTPException(status_code=403, detail='Maintainer role required')
    try:
        res = crud.delete_bike(db, bike_id=bike_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not res:
        raise HTTPException(status_code=404, detail='Bike not found')
    return {'status':'deleted'}


@app.post('/api/bikes/{bike_id}/status')
def post_bike_status(bike_id: int, payload: dict, db: Session = Depends(get_db), user = Depends(get_current_user)):
    if not getattr(user, 'is_maintainer', False):
        raise HTTPException(status_code=403, detail='Maintainer role required')
    status_val = payload.get('status')
    if not status_val:
        raise HTTPException(status_code=400, detail='Missing status')
    try:
        bike = crud.set_bike_status(db, bike_id=bike_id, status=status_val, maintainer_id=getattr(user,'id', None))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return bike


@app.get('/api/maintenances', response_model=list[schemas.MaintenanceOut])
def list_maintenances(db: Session = Depends(get_db), user = Depends(get_current_user)):
    # only maintainers can view maintenance records
    if not getattr(user, 'is_maintainer', False):
        raise HTTPException(status_code=403, detail='Maintainer role required')
    from .crud import list_maintenances
    raw = list_maintenances(db)
    out = []
    for m in raw:
        out.append({
            'id': m.id,
            'bike_id': m.bike_id,
            'maintainer_id': m.maintainer_id,
            'start_time': m.start_time,
            'end_time': m.end_time,
            'maintainer_username': getattr(m.maintainer, 'username', None) if getattr(m, 'maintainer', None) else None
        })
    return out


@app.post('/api/rentals')
def start_rental(r_in: schemas.RentalCreate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    try:
        rental = crud.rent_bike(db=db, user_id=user.id if hasattr(user,'id') else getattr(user,'user_id'), bike_id=r_in.bike_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return rental


@app.post('/api/rentals/{rental_id}/return')
def end_rental(rental_id: int, rating: Optional[int] = Body(None, embed=True), db: Session = Depends(get_db), user = Depends(get_current_user)):
    try:
        # allow None or integer 0-5
        if rating is not None:
            try:
                rating = int(rating)
                if rating < 0 or rating > 5:
                    raise ValueError()
            except Exception:
                raise HTTPException(status_code=400, detail='rating must be integer 0-5')
        res = crud.return_bike_with_rating(db=db, rental_id=rental_id, rating=rating)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return res


@app.get('/api/rentals/me', response_model=list[schemas.RentalOut])
def my_rentals(db: Session = Depends(get_db), user = Depends(get_current_user)):
    # return rentals for current user
    uid = user.id if hasattr(user,'id') else getattr(user,'user_id')
    rentals = crud.get_user_rentals(db, user_id=uid)
    return rentals


@app.get('/')
def root():
    return {'status':'ok', 'ui':'/static/gui.html'}
