from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from .. import models, utils, schemas
from ..database import get_db
from ..services import mail_service

router = APIRouter(prefix="/password", tags=["Forgot Password"])

#send otp on email
@router.post("/forgot")
def forgot_password(
    request: schemas.ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.email == request.email
    ).first()

    if not user:
        return {"message": "If the email exists, an OTP has been sent"}

    otp_code = utils.generate_otp()
    otp_expiry = utils.otp_expiry_time(minutes=3)

    user.reset_token = otp_code
    user.reset_token_expiry = otp_expiry

    db.commit()

    try:
        mail_service.send_forgot_password_otp_email(user.email, otp_code)
    except Exception as e:
        user.reset_token = None
        user.reset_token_expiry = None
        db.commit()
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Please try again later."
        )

    return {"message": "OTP sent to email"}

#verify if otp is correct or not
@router.post("/verify-otp")
def verify_otp(
    request: schemas.ForgotPasswordVerifyOTP,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.email == request.email
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or OTP")

    if user.reset_token != request.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user.reset_token_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired")

    return {"message": "OTP verified successfully"}


#  RESET PASSWORD
@router.post("/reset")
def reset_password(
    request: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.email == request.email
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or OTP")

    if user.reset_token != request.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user.reset_token_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired")

    hashed_password = utils.hash_pass(request.new_password)

    user.password = hashed_password
    user.reset_token = None
    user.reset_token_expiry = None

    db.commit()

    return {"message": "Password reset successfully"}
