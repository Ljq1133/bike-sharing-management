from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from typing import Optional
from .security import get_password_hash, verify_password, create_access_token
import math

app = FastAPI()

# In-memory stores (demo)
USERS = {}  # username -> {id, username, hashed_password, is_maintainer}
BIKES = {}  # id -> {id, lat, lng, status}
RENTALS = {}  # id -> {id, user, bike, start_time, end_time, status}
_uid = 1
_bid = 1
_rid = 1


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    import math
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_user_by_username(username: str):
    return USERS.get(username)


def require_user(token: Optional[str] = None):
    # token is raw JWT encoding username in 'sub'
    from jose import jwt, JWTError
    from .security import SECRET_KEY, ALGORITHM
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@app.post('/api/users')
async def register(request: Request):
    data = await request.json()
    username = data.get('username')
    password = data.get('password')
    is_maintainer = bool(data.get('is_maintainer', False))
    if not username or not password:
        raise HTTPException(status_code=400, detail='username/password required')
    # username must be unique
    if username in USERS:
        raise HTTPException(status_code=409, detail='username exists')
    # password policy: >8 chars, contains letter and digit
    if len(password) <= 8 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail='password must be >8 characters and include letters and digits')
    global _uid
    USERS[username] = {'id': _uid, 'username': username, 'hashed_password': get_password_hash(password), 'is_maintainer': is_maintainer}
    _uid += 1
    return {'id': USERS[username]['id'], 'username': username, 'is_maintainer': is_maintainer}


@app.post('/api/auth/login')
async def login(username: str = Form(...), password: str = Form(...)):
    user = get_user_by_username(username)
    if not user or not verify_password(password, user['hashed_password']):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    token = create_access_token({'sub': username})
    return {'access_token': token, 'token_type': 'bearer'}


@app.get('/api/bikes/nearby')
def bikes_nearby(lat: float, lng: float, radius_km: float = 1.0):
    out = []
    for b in BIKES.values():
        d = haversine(lat, lng, b['lat'], b['lng'])
        if d <= radius_km:
            out.append({'id': b['id'], 'lat': b['lat'], 'lng': b['lng'], 'status': b['status']})
    return out


@app.post('/api/bikes')
async def create_bike(lat: float, lng: float, token: Optional[str] = None):
    user = require_user(token)
    global _bid
    BIKES[_bid] = {'id': _bid, 'lat': lat, 'lng': lng, 'status': 'available'}
    _bid += 1
    return BIKES[_bid-1]


@app.post('/api/rentals')
async def rent_bike(payload: dict, token: Optional[str] = None):
    user = require_user(token)
    bike_id = payload.get('bike_id')
    bike = BIKES.get(bike_id)
    if not bike or bike['status'] != 'available':
        raise HTTPException(status_code=400, detail='bike not available')
    bike['status'] = 'in_use'
    global _rid
    RENTALS[_rid] = {'id': _rid, 'user_id': user['id'], 'bike_id': bike_id, 'start_time': datetime.utcnow().isoformat(), 'end_time': None, 'status': 'ongoing'}
    _rid += 1
    return {'rental_id': _rid-1}


@app.post('/api/rentals/{rental_id}/return')
def return_rental(rental_id: int, token: Optional[str] = None):
    user = require_user(token)
    rental = RENTALS.get(rental_id)
    if not rental or rental['user_id'] != user['id']:
        raise HTTPException(status_code=404, detail='rental not found')
    rental['status'] = 'returned'
    rental['end_time'] = datetime.utcnow().isoformat()
    bike = BIKES.get(rental['bike_id'])
    if bike:
        bike['status'] = 'available'
    return {'ok': True}


@app.post('/api/bikes/{bike_id}/status')
async def set_bike_status(bike_id: int, payload: dict, token: Optional[str] = None):
    user = require_user(token)
    if not user.get('is_maintainer'):
        raise HTTPException(status_code=403, detail='maintainer only')
    status_val = payload.get('status')
    bike = BIKES.get(bike_id)
    if not bike:
        raise HTTPException(status_code=404, detail='bike not found')
    bike['status'] = status_val
    return {'ok': True}


@app.get('/api/me')
def me(token: Optional[str] = None):
    user = require_user(token)
    return {'id': user['id'], 'username': user['username'], 'is_maintainer': user['is_maintainer']}


# serve static GUI
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get('/')
def root():
    return {'status': 'ok', 'ui': '/static/gui.html'}
