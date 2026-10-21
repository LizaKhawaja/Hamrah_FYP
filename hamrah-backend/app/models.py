from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Float, func, ForeignKey, DateTime, Boolean, JSON, UniqueConstraint
from .database import Base
from sqlalchemy.orm import relationship

class DSUStudent(Base):
    __tablename__ = "dsu_students"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    dsu_reg_id = Column(String(20), nullable=False, unique=True, index=True)
    department = Column(String(50), nullable=True)
    gender = Column(String(10))
    email = Column(String(100))

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    dsu_reg_id = Column(String(20), nullable=False, unique=True)
    phone_number = Column(String(15), nullable=False, unique=True, index=True)
    email = Column(String(100), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)
    gender = Column(String(50), nullable=False)

    is_passenger = Column(Boolean, default=True)  
    is_driver = Column(Boolean, default=False)     

    role = Column(String(10), nullable=False, server_default="passenger")

    nic_image_url = Column(Text, nullable=True)
    live_image_url = Column(Text, nullable=True)
    license_image_url = Column(Text, nullable=True)

    is_verified = Column(Boolean, default=False)
    otp_code = Column(String(6), nullable=True)
    otp_expiry = Column(DateTime, nullable=True)

    reset_token = Column(String(255), nullable=True)
    reset_token_expiry = Column(DateTime, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    vehicles = relationship("Vehicle", back_populates="user", cascade="all, delete")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    mode_of_transport = Column(String(10), nullable=False)  # car / bike
    vehicle_number = Column(String(20), nullable=False, unique=True)
    vehicle_colour = Column(String(20), nullable=False)
    vehicle_model = Column(String(20), nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="vehicles")

    
class Ride(Base):
    __tablename__ = "rides"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)

    from_address = Column(String, nullable=False)
    from_lat = Column(Float, nullable=False)
    from_lng = Column(Float, nullable=False)

    to_address = Column(String, nullable=False)
    to_lat = Column(Float, nullable=False)
    to_lng = Column(Float, nullable=False)

    departure_time = Column(DateTime, nullable=False)
    seats_available = Column(Integer, nullable=False)

    ac = Column(Boolean, nullable=True)
    gender_filter = Column(String, default="any")
    fare_per_seat = Column(Float, default=0.0)
    
    status = Column(String, nullable=False, default="active")  # active/full/cancelled/completed

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    driver = relationship("User")
    vehicle = relationship("Vehicle")

    @property
    def mode_of_transport(self):
     return self.vehicle.mode_of_transport


class RideRequest(Base):
    __tablename__ = "ride_requests"

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    pickup_lat = Column(Float, nullable=True)
    pickup_lng = Column(Float, nullable=True)

    status = Column(String, default="pending")  # pending/accepted/rejected/cancelled
    distance_from_route = Column(Float, default=0.0)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    ride = relationship("Ride")
    passenger = relationship("User")


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    token = Column(Text)


class RideLocation(Base):
    __tablename__ = "ride_locations"

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now())

    ride = relationship("Ride")
    driver = relationship("User")


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stars = Column(Integer, nullable=False)
    tags = Column(JSON, nullable=True)
    review = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    ride = relationship("Ride")
    passenger = relationship("User", foreign_keys=[passenger_id])
    driver = relationship("User", foreign_keys=[driver_id])

    __table_args__ = (
        UniqueConstraint("ride_id", "passenger_id", name="uq_rating_ride_passenger"),
    )


class PassengerRating(Base):
    __tablename__ = "passenger_ratings"

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stars = Column(Integer, nullable=False)
    tags = Column(JSON, nullable=True)
    review = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    ride = relationship("Ride")
    passenger = relationship("User", foreign_keys=[passenger_id])
    driver = relationship("User", foreign_keys=[driver_id])

    __table_args__ = (
        UniqueConstraint("ride_id", "passenger_id", name="uq_passenger_rating_ride_passenger"),
    )



class RidePickupPoint(Base):
    __tablename__ = "ride_pickup_points"

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    address = Column(Text, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    order_index = Column(Integer, default=0)

    ride = relationship("Ride")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    ride = relationship("Ride")
    sender = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    type = Column(String(50), nullable=False)   
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)           

    is_read = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User")
