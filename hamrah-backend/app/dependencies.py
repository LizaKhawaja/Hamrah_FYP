from fastapi import Depends, HTTPException
from . import models, oauth2

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from . import models, oauth2, database

def require_driver(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db)
):
    if not current_user.is_driver or current_user.role != "driver":
        raise HTTPException(status_code=403, detail="Driver mode required")

    if not current_user.nic_image_url or not current_user.live_image_url or not current_user.license_image_url:
        raise HTTPException(status_code=403, detail="Complete driver verification first")

    has_vehicle = db.query(models.Vehicle).filter(models.Vehicle.user_id == current_user.id).first()
    if not has_vehicle:
        raise HTTPException(status_code=403, detail="Add at least 1 vehicle to continue")

    return current_user

def require_passenger(current_user: models.User = Depends(oauth2.get_current_user)):
    if not current_user.is_passenger or current_user.role != "passenger":
        raise HTTPException(status_code=403, detail="Passenger mode required")
    return current_user