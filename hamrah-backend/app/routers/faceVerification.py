import os
import shutil
import uuid
import requests
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.face_verification.service import (
    extract_face_from_id_card,
    extract_face,
    compare_faces,
    capture_live_image,
    check_duplicate_face,
)
from .. import schemas

router = APIRouter(
    prefix="/face-verification",
    tags=["Face Verification"],
)

#download image from url and save on local system
def _download_image(url: str, save_path: str):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid image URL")

    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Unable to download image")
        with open(save_path, "wb") as f:
            f.write(response.content)
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Image download error: {str(e)}")

#compare NIC image and live webcam image
@router.post("/verify-cnic")
def verify_cnic(cnic_image: UploadFile = File(...)):
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    cnic_path = os.path.join(upload_dir, f"cnic_{cnic_image.filename}")

    try:
        with open(cnic_path, "wb") as f:
            f.write(cnic_image.file.read())

        id_face_path = extract_face_from_id_card(cnic_path)
        if not id_face_path:
            return {"verified": False, "message": "No face detected on CNIC"}

        live_image_path = capture_live_image()
        if not live_image_path:
            return {"verified": False, "message": "Live face not detected (webcam required)"}

        live_face_path = extract_face(live_image_path, face_type="live")
        if not live_face_path:
            return {"verified": False, "message": "No face detected in live image"}

        is_match, distance = compare_faces(id_face_path, live_face_path)

        if not is_match:
            return {
                "verified": False,
                "message": "Face verification failed",
                "distance": distance,
            }

        return {
            "verified": True,
            "message": "Face verified successfully",
            "distance": distance,
        }
    except Exception as e:
        return {"verified": False, "message": f"Face verification error: {e}"}
    finally:
        shutil.rmtree("temp_faces", ignore_errors=True)

#compare already uploaded urls
@router.post("/verify", response_model=schemas.FaceVerifyResponse)
def verify_face_urls(payload: schemas.FaceVerifyRequest):

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    cnic_path = os.path.join(upload_dir, f"verify_cnic_{uuid.uuid4()}.jpg")
    live_path = os.path.join(upload_dir, f"verify_live_{uuid.uuid4()}.jpg")

    try:
        _download_image(payload.cnic_image_url, cnic_path)
        _download_image(payload.live_image_url, live_path)

        id_face = extract_face(cnic_path, face_type="id")
        live_face = extract_face(live_path, face_type="live")

        if not id_face or not live_face:
            return schemas.FaceVerifyResponse(
                verified=False,
                message="Face not detected in one or both images",
            )

        is_match, distance = compare_faces(id_face, live_face)
        print(f"[FACE VERIFY] distance={distance:.4f}, is_match={is_match}")

        if not is_match:
            return schemas.FaceVerifyResponse(
                verified=False,
                distance=round(distance, 4),
                message="Face verification failed — faces do not match",
            )

        return schemas.FaceVerifyResponse(
            verified=True,
            distance=round(distance, 4),
            message="Face verified successfully",
        )
    except Exception as e:
        return schemas.FaceVerifyResponse(
            verified=False,
            message=f"Face verification error: {e}",
        )
    finally:
        shutil.rmtree("temp_faces", ignore_errors=True)
