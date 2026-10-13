from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .db import Base


class BikeStatus(str, enum.Enum):
    available = "available"
    in_use = "in_use"
    maintenance = "maintenance"


class RentalStatus(str, enum.Enum):
    ongoing = "ongoing"
    returned = "returned"


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_maintainer = Column(Boolean, default=False, nullable=False)
    active_jti = Column(String, nullable=True)
    rentals = relationship("Rental", back_populates="user")


class Bike(Base):
    __tablename__ = "bikes"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    status = Column(Enum(BikeStatus), default=BikeStatus.available, nullable=False)
    usage_count = Column(Integer, default=0)
    # score/评分: 默认 5
    rating = Column(Float, default=5.0)
    rentals = relationship("Rental", back_populates="bike")


class Maintenance(Base):
    __tablename__ = "maintenances"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True, index=True)
    bike_id = Column(Integer, ForeignKey("bikes.id"), nullable=False)
    maintainer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)

    bike = relationship("Bike")
    maintainer = relationship("User")

    @property
    def maintainer_username(self):
        try:
            return self.maintainer.username if self.maintainer else None
        except Exception:
            return None


class Rental(Base):
    __tablename__ = "rentals"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bike_id = Column(Integer, ForeignKey("bikes.id"), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    rating = Column(Integer, nullable=True)
    status = Column(Enum(RentalStatus), default=RentalStatus.ongoing, nullable=False)

    user = relationship("User", back_populates="rentals")
    bike = relationship("Bike", back_populates="rentals")
