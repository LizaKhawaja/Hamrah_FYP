from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from . import models
from .routers import auth, user, calls, faceVerification, rides, ride_request, forgot_password, notifications, location, ratings, calls, sos, upload, license_ocr, chat, vehicles, drivers
import firebase_admin
from firebase_admin import credentials
from app.routers import recommendations
from contextlib import asynccontextmanager
from app.scheduler import start_scheduler, stop_scheduler
import os
import logging
import re


class MaskTokenFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(
                re.sub(r"([?&]token=)[^&\s]+", r"\1***", arg)
                if isinstance(arg, str)
                else arg
                for arg in record.args
            )
        elif isinstance(record.args, dict):
            record.args = {
                key: (
                    re.sub(r"([?&]token=)[^&\s]+", r"\1***", value)
                    if isinstance(value, str)
                    else value
                )
                for key, value in record.args.items()
            }
        return True


logging.getLogger("uvicorn.access").addFilter(MaskTokenFilter())

models.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app):
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(forgot_password.router)
app.include_router(user.router)
app.include_router(faceVerification.router)
app.include_router(rides.router)
app.include_router(ride_request.router)
app.include_router(notifications.router)
app.include_router(location.router)
app.include_router(recommendations.router)
app.include_router(ratings.router)
app.include_router(ratings.reviews_router)
app.include_router(calls.router)
app.include_router(sos.router)
app.include_router(upload.router)
app.include_router(license_ocr.router)
app.include_router(chat.router)
app.include_router(vehicles.router)
app.include_router(drivers.router)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

_firebase_key = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "firebase_key.json")
if os.path.exists(_firebase_key):
    cred = credentials.Certificate(_firebase_key)
    firebase_admin.initialize_app(cred)
    print(f"[Firebase] initialized: {cred.project_id}")
else:
    print(f"[Firebase] key not found: {_firebase_key}")

