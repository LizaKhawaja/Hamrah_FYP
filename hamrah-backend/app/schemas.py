from pydantic import BaseModel, EmailStr, field_validator
from enum import Enum
from typing import Optional, List, Literal
from datetime import datetime

TransportMode = Literal["car", "bike"]

class RideStatus(str, Enum):
    active = "active"
    full = "full"
    cancelled = "cancelled"
    completed = "completed"

class RideRequestStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    confirmed = "confirmed"
    picked_up = "picked_up"
    completed = "completed"
    rejected = "rejected"
    cancelled_by_passenger = "cancelled_by_passenger"
    cancelled_by_driver = "cancelled_by_driver"

class UserBase(BaseModel):
    first_name: str
    last_name: str
    dsu_reg_id: str
    phone_number: str
    email: EmailStr
    gender: str

class VehicleCreate(BaseModel):
    vehicle_number: str
    mode_of_transport: TransportMode
    vehicle_model: Optional[str] = None
    vehicle_colour: Optional[str] = None
class VehicleCreateWithId(BaseModel):
    id: Optional[int] = None          
    vehicle_number: str
    mode_of_transport: TransportMode
    vehicle_model: Optional[str] = None
    vehicle_colour: Optional[str] = None

class VehicleOut(BaseModel):
    id: int
    vehicle_number: str
    mode_of_transport: str
    vehicle_model: Optional[str] = None
    vehicle_colour: Optional[str] = None
    class Config:
        from_attributes = True

class DriverCreate(UserBase):
    password: str
    license_image_url: str
    cnic_image_url: str
    live_image_url: str
    vehicles: List[VehicleCreate]


class PassengerCreate(UserBase):
    password: str

class DriverEnable(BaseModel):
    dsu_reg_id: str
    license_image_url: str
    cnic_image_url: str
    live_image_url: str
    vehicles: List[VehicleCreate]
    email: Optional[str] = None  

class MeOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    dsu_reg_id: str
    phone_number: str
    email: EmailStr
    gender: str
    is_passenger: bool
    is_driver: bool
    active_mode: str
    driver_profile_complete: bool
    vehicles: Optional[List["VehicleOut"]] = []
    total_rides: Optional[int] = 0

class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None

class SwitchMode(BaseModel):
    mode: Literal["passenger", "driver"]


class UserOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    dsu_reg_id: str
    phone_number: str
    role: str
    is_passenger: bool
    is_driver: bool

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    id: int


class OTPVerify(BaseModel):
    email: EmailStr
    otp_code: str


class ResendOTP(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordVerifyOTP(BaseModel):
    email: EmailStr
    otp_code: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str
    new_password: str

class PickupPointCreate(BaseModel):
    address: str
    lat: float
    lng: float
    order_index: int = 0

class RideCreate(BaseModel):
    vehicle_id: int
    from_address: str
    from_lat: float
    from_lng: float
    to_address: str
    to_lat: float
    to_lng: float
    departure_time: datetime
    seats_available: Optional[int] = None     
    ac: Optional[bool] = None
    gender_filter: str = "any"
    fare_per_seat: float = 0.0
    pickup_points: Optional[List[PickupPointCreate]] = []

    @field_validator("fare_per_seat")
    def validate_fare(cls, v):
        if v < 0:
            raise ValueError("fare_per_seat cannot be negative")
        return v

class RideOut(BaseModel):
    id: int
    driver_id: int
    vehicle_id: int
    from_address: str
    to_address: str
    departure_time: datetime
    seats_available: int
    ac: Optional[bool] = None
    gender_filter: Optional[str] = None
    fare_per_seat: float
    mode_of_transport: Optional[str] = None
    status: Optional[str] = None
    driver_name: Optional[str] = None
    driver_rating: Optional[float] = None
    driver_phone: Optional[str] = None
    vehicle_number: Optional[str] = None
    pickup_points: Optional[List[PickupPointCreate]] = []
    total_rides: Optional[int] = 0

    class Config:
        from_attributes = True

class RideRequestCreate(BaseModel):
    ride_id: int
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None

class RideRequestOut(BaseModel):
    id: int
    ride_id: int
    status: RideRequestStatus
    distance_from_route: float

    class Config:
        from_attributes = True


class TokenRequest(BaseModel):   #notification system
    user_id: int
    token: str

class LocationUpdate(BaseModel):
    ride_id: int
    latitude: float
    longitude: float
    driver_id: int

class LocationResponse(BaseModel):
    ride_id: int
    driver_id: int
    latitude: float
    longitude: float
    eta_seconds: Optional[int] = None
    eta_minutes: Optional[int] = None

    class Config:
        from_attributes = True


class RatingCreate(BaseModel):
    ride_id: int
    stars: int
    tags: Optional[List[str]] = []
    review: Optional[str] = None

    @field_validator("stars")
    def validate_stars(cls, v):
        if v < 1 or v > 5:
            raise ValueError("stars must be between 1 and 5")
        return v


class RatingOut(BaseModel):
    id: int
    ride_id: int
    passenger_id: int
    driver_id: int
    stars: int
    tags: Optional[List[str]] = []
    review: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PassengerRatingCreate(BaseModel):
    ride_id: int
    passenger_id: int
    stars: int
    tags: Optional[List[str]] = []
    review: Optional[str] = None

    @field_validator("stars")
    def validate_stars(cls, v):
        if v < 1 or v > 5:
            raise ValueError("stars must be between 1 and 5")
        return v


class PassengerRatingOut(BaseModel):
    id: int
    ride_id: int
    passenger_id: int
    driver_id: int
    stars: int
    tags: Optional[List[str]] = []
    review: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DriverRatingStats(BaseModel):
    driver_id: int
    average_rating: float
    total_ratings: int


class UnratedRideOut(BaseModel):
    ride_id: int
    request_id: int
    driver_id: int
    driver_name: str
    vehicle_number: Optional[str] = ""
    from_address: Optional[str] = ""
    to_address: Optional[str] = ""
    fare: float
    completed_at: Optional[str] = None


class FaceVerifyRequest(BaseModel):
    cnic_image_url: str
    live_image_url: str


class FaceVerifyResponse(BaseModel):
    verified: bool
    distance: Optional[float] = None
    message: str


class LicenseVerifyRequest(BaseModel):
    license_image_url: str
    cnic_number: Optional[str] = None


class LicenseExtractedData(BaseModel):
    name: Optional[str] = None
    license_number: Optional[str] = None
    cnic: Optional[str] = None
    father_name: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    blood_group: Optional[str] = None


class LicenseVerifyResponse(BaseModel):
    verified: bool
    extracted: LicenseExtractedData
    is_expired: Optional[bool] = None
    confidence: float = 0.0
    message: Optional[str] = None
    raw_text: Optional[str] = None
class TokenRequest(BaseModel):
    token: str = None
    fcm_token: str = None

    def get_token(self):
        return self.token or self.fcm_token
