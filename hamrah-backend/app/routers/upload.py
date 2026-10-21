import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Request

router = APIRouter(prefix="/upload", tags=["Upload"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/")
async def upload_image(image: UploadFile = File(...), request: Request = None):
    ext = os.path.splitext(image.filename or ".jpg")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    contents = await image.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 5 MB allowed.")

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    unique_name = f"{uuid.uuid4()}{ext}"
    save_path = os.path.join(upload_dir, unique_name)

    with open(save_path, "wb") as f:
        f.write(contents)

    base_url = str(request.base_url).rstrip("/") if request else ""
    file_url = f"{base_url}/uploads/{unique_name}"

    return {
        "url": file_url,
        "filename": unique_name,
    }
