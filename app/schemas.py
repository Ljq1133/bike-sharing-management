from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from enum import Enum


class BikeStatus(str, Enum):
    available = "available"
    in_use = "in_use"
    maintenance = "maintenance"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=256)
    is_maintainer: Optional[bool] = False
    invite_code: Optional[str] = None

    @validator('password')
    def password_bytes_length(cls, v: str) -> str:
        if len(v.encode('utf-8')) > 1024:
            raise ValueError('password too long (max 1024 bytes)')
        return v


class UserOut(BaseModel):
    id: int
    username: str
    is_maintainer: bool

    class Config:
        orm_mode = True


class BikeCreate(BaseModel):
    # accept either `latitude`/`longitude` or `lat`/`lng` from frontend
    latitude: Optional[float]
    longitude: Optional[float]
    lat: Optional[float] = None
    lng: Optional[float] = None


class BikeOut(BaseModel):
    id: int
    lat: float
    lng: float
    status: BikeStatus
    usage_count: int
    rating: float

    class Config:
        orm_mode = True


class RentalCreate(BaseModel):
    bike_id: int


class RentalOut(BaseModel):
    id: int
    user_id: int
    bike_id: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    status: str
    rating: Optional[int]

    class Config:
        orm_mode = True


class MaintenanceOut(BaseModel):
    id: int
    bike_id: int
    maintainer_id: Optional[int]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    maintainer_username: Optional[str]
    maintainer_username: Optional[str]

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


class UserLogin(BaseModel):
    username: str
    password: str
