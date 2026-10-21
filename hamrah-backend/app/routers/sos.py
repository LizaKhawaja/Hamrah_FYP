from fastapi import APIRouter
from ..config import settings

router = APIRouter(prefix="/sos", tags=["SOS"])


@router.get("/contacts")
def get_sos_contacts():
    return [
        {"name": "Police Emergency", "number": settings.sos_police_number},
        {"name": "Hamrah Support", "number": settings.sos_hamrah_support_number},
        {"name": "Campus Security", "number": settings.sos_campus_security_number},
    ]
