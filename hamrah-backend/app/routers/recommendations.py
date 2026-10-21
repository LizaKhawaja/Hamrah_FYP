from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DeviceToken, User
from app.services.recommendation_service import run_recommendations
from app import oauth2

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

#runs real recommendation system
@router.post("/run")
def trigger_recommendations(
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user)  
):
    results = run_recommendations(db)

    if not results:
        return {
            "message": "No recommendations generated.",
            "detail": "Either no passengers have ride history, or no matching future rides found.",
            "recommendations": []
        }

    return {
        "message": f"Recommendations processed for {len(results)} passenger(s).",
        "recommendations": results
    }

#test ending point
@router.post("/test-run")
def test_recommendations(db: Session = Depends(get_db)):
    results = run_recommendations(db)
    return {
        "message": f"Test recommendations processed for {len(results)} passenger(s).",
        "recommendations": results
    }

#check device token
@router.get("/debug/tokens")
def debug_tokens(db: Session = Depends(get_db)):
    tokens = (
        db.query(DeviceToken, User)
        .join(User, User.id == DeviceToken.user_id)
        .all()
    )
    return {
        "count": len(tokens),
        "tokens": [
            {
                "user_id": u.id,
                "user_name": f"{u.first_name} {u.last_name}",
                "user_email": u.email,
                "token_preview": (t.token[:30] + "...") if t.token else "",
                "token_length": len(t.token) if t.token else 0,
            }
            for t, u in tokens
        ]
    }

#delete invalid and expired token
@router.delete("/debug/tokens/{user_id}")
def delete_user_tokens(user_id: int, db: Session = Depends(get_db)):
    deleted = (
        db.query(DeviceToken)
        .filter(DeviceToken.user_id == user_id)
        .delete()
    )
    db.commit()
    return {"deleted": deleted, "user_id": user_id}