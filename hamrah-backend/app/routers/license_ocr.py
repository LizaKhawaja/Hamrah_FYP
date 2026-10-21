import os
import re
import uuid
import requests
from datetime import datetime
from fastapi import APIRouter, HTTPException
from .. import schemas

router = APIRouter(prefix="/license", tags=["License OCR"])

_reader = None

def _get_reader():   #load ocr engine EasyOCR
    global _reader
    if _reader is None:
        try:
            import easyocr
            _reader = easyocr.Reader(["en"], gpu=False)
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="EasyOCR not installed. Run: pip install easyocr",
            )
    return _reader

#download image from url
def _download_image(url: str, save_path: str):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid image URL")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            raise HTTPException(status_code=400, detail="Unable to download image")
        with open(save_path, "wb") as f:
            f.write(r.content)
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Image download error: {str(e)}")

#finding useful info using regex
def _extract_fields(raw_text: str) -> schemas.LicenseExtractedData:

    text = raw_text.replace("\n", " ").replace("  ", " ").strip()

    license_number = None
    lic_patterns = [
        r"[A-Z]{2,3}[- ]?\d{5,8}",       
        r"\d{4}[- ]\d{7}[- ]\d{1}",   
        r"[A-Z]{1,2}\d{6,8}",              
    ]
    for pat in lic_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            license_number = m.group()
            break

    cnic = None
    cnic_m = re.search(r"\d{5}[- ]?\d{7}[- ]?\d{1}", text)
    if cnic_m:
        cnic = cnic_m.group().replace(" ", "-")
        if "-" not in cnic:
            cnic = f"{cnic[:5]}-{cnic[5:12]}-{cnic[12]}"

    dates = re.findall(r"\d{2}[-/\.]\d{2}[-/\.]\d{4}|\d{4}[-/\.]\d{2}[-/\.]\d{2}", text)
    issue_date = None
    expiry_date = None
    if len(dates) >= 2:
        issue_date = dates[0]
        expiry_date = dates[1]
    elif len(dates) == 1:
        expiry_date = dates[0]

    blood_group = None
    bg_m = re.search(r"(?:blood|blod)\s*(?:group|grp)?\s*[:\s]*([ABOabo]{1,2}[+-])", text, re.IGNORECASE)
    if not bg_m:
        bg_m = re.search(r"\b([ABOabo]{1,2}[+-])\b", text)
    if bg_m:
        blood_group = bg_m.group(1).upper()

    name = None
    father_name = None
    lines = raw_text.strip().split("\n")
    name_keywords = ["name", "holder", "license", "driving", "nama", "نام"]

    for i, line in enumerate(lines):
        line_clean = line.strip()
        if any(kw in line_clean.lower() for kw in ["islam", "republic", "pakistan", "authority", "govt"]):
            continue
        if line_clean.isupper() and len(line_clean.split()) >= 2 and len(line_clean) > 5:
            if not any(c.isdigit() for c in line_clean):
                if name is None:
                    name = line_clean.title()
                elif father_name is None and line_clean != line_clean.upper():
                    pass  

    if name is None:
        for line in lines:
            clean = line.strip()
            words = clean.split()
            if 2 <= len(words) <= 4 and all(w.isalpha() for w in words) and len(clean) > 5:
                if not any(kw in clean.lower() for kw in name_keywords):
                    name = clean.title()
                    break

    return schemas.LicenseExtractedData(
        name=name,
        license_number=license_number,
        cnic=cnic,
        father_name=father_name,
        issue_date=issue_date,
        expiry_date=expiry_date,
        blood_group=blood_group,
    )

#checks license expiry
def _is_expired(expiry_str: str):
    if not expiry_str:
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            expiry_dt = datetime.strptime(expiry_str, fmt)
            return expiry_dt < datetime.now()
        except ValueError:
            continue
    return None

# Image → Text → Data extract → Verify
@router.post("/verify", response_model=schemas.LicenseVerifyResponse)
def verify_license(payload: schemas.LicenseVerifyRequest):

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    img_path = os.path.join(upload_dir, f"license_{uuid.uuid4()}.jpg")

    try:
        _download_image(payload.license_image_url, img_path)
        reader = _get_reader()

        import cv2 as _cv2
        _img = _cv2.imread(img_path)
        _gray = _cv2.cvtColor(_img, _cv2.COLOR_BGR2GRAY)

        results = reader.readtext(_gray, detail=1)
        raw_text = " ".join([r[1] for r in results])
        confidences = [r[2] for r in results if len(r) > 2]
        avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

        if not raw_text.strip():
            return schemas.LicenseVerifyResponse(
                verified=False,
                extracted=schemas.LicenseExtractedData(),
                message="No text could be extracted from the image",
                confidence=0.0,
            )

        extracted = _extract_fields(raw_text)
        expired = _is_expired(extracted.expiry_date)

        if expired is True:
            return schemas.LicenseVerifyResponse(
                verified=False,
                extracted=extracted,
                is_expired=True,
                confidence=avg_confidence,
                message="License is expired. Please renew your license.",
            )

        if payload.cnic_number and extracted.cnic:
            def _normalize(c): return re.sub(r"[-\s]", "", c or "")
            if _normalize(extracted.cnic) != _normalize(payload.cnic_number):
                return schemas.LicenseVerifyResponse(
                    verified=False,
                    extracted=extracted,
                    is_expired=expired,
                    confidence=avg_confidence,
                    message="CNIC number on license does not match. Please use your own license.",
                )

        verified = bool(extracted.license_number or extracted.cnic)

        return schemas.LicenseVerifyResponse(
            verified=verified,
            extracted=extracted,
            is_expired=expired,
            confidence=avg_confidence,
            message="License verified successfully" if verified else "Could not extract license fields — please retake photo",
            raw_text=raw_text if not verified else None,
        )

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)

#check if ocr is working or not
@router.get("/health")
def license_health():
    try:
        import easyocr
        return {"status": "ok", "engine": "easyocr"}
    except ImportError:
        return {"status": "unavailable", "engine": None}
