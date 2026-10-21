import os
import cv2
from PIL import Image

_yolo_model = None
_arcface_ready = False


def _load_yolo_model(model_path: str = None):
    if model_path is None:
        possible_paths = [
            "best.pt",
            "Main/best.pt",
            "beta-testing/best.pt",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                model_path = path
                break

    if model_path is None:
        raise FileNotFoundError("YOLO model (best.pt) not found")

    from ultralytics import YOLO
    return YOLO(model_path)


def _get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        _yolo_model = _load_yolo_model()
    return _yolo_model


def _ensure_arcface():
    global _arcface_ready
    if not _arcface_ready:
        from deepface import DeepFace
        DeepFace.build_model("ArcFace")
        _arcface_ready = True


def extract_face(image_path: str, face_type: str):
    yolo_model = _get_yolo_model()

    if face_type == "id":
        conf = 0.10
        imgsz = 1280
    else:
        conf = 0.25
        imgsz = 640

    results = yolo_model.predict(image_path, conf=conf, imgsz=imgsz, verbose=False)[0]
    image = Image.open(image_path)

    temp_dir = "temp_faces"
    os.makedirs(temp_dir, exist_ok=True)

    if not hasattr(results, "boxes") or results.boxes is None or len(results.boxes.xyxy) == 0:
        return None

    x1, y1, x2, y2 = map(int, results.boxes.xyxy[0])

    w = x2 - x1
    h = y2 - y1
    pad_x = int(w * 0.10)
    pad_y = int(h * 0.10)
    img_w, img_h = image.size
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(img_w, x2 + pad_x)
    y2 = min(img_h, y2 + pad_y)

    face_img = image.crop((x1, y1, x2, y2))
    face_img = face_img.resize((224, 224), Image.LANCZOS)

    if face_type == "id":
        from PIL import ImageEnhance
        face_img = ImageEnhance.Contrast(face_img).enhance(1.5)
        face_img = ImageEnhance.Sharpness(face_img).enhance(2.0)
        face_img = ImageEnhance.Brightness(face_img).enhance(1.1)

    face_path = os.path.join(temp_dir, f"{face_type}_face.jpg")
    face_img.save(face_path, quality=95)

    return face_path


def extract_face_from_id_card(id_card_path: str):
    return extract_face(image_path=id_card_path, face_type="id")


def compare_faces(face1_path: str, face2_path: str):
    from deepface import DeepFace

    _ensure_arcface()

    result = DeepFace.verify(
        img1_path=face1_path,
        img2_path=face2_path,
        model_name="ArcFace",
        enforce_detection=False,
        distance_metric="cosine",
    )

    distance = result["distance"]
    is_match = distance < 0.85

    return is_match, distance


def check_duplicate_face(new_face_path: str, db, exclude_user_id=None):
    from app import models

    query = db.query(models.User).filter(models.User.role == "driver")

    if exclude_user_id:
        query = query.filter(models.User.id != exclude_user_id)

    existing_drivers = query.all()

    for user in existing_drivers:
        if not user.nic_image_url:
            continue

        try:
            stored_face = extract_face(user.nic_image_url, face_type="stored")
            if not stored_face:
                continue

            is_match, distance = compare_faces(stored_face, new_face_path)
            if is_match:
                print("Duplicate face detected. Distance:", distance)
                return True
        except Exception:
            continue

    return False


def capture_live_image(save_path: str = "uploads/live.jpg", timeout: int = 10):
    os.makedirs("uploads", exist_ok=True)

    cam = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    start_time = cv2.getTickCount()
    freq = cv2.getTickFrequency()

    while True:
        ret, frame = cam.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) == 1:
            cv2.imwrite(save_path, frame)
            break

        elapsed = (cv2.getTickCount() - start_time) / freq
        if elapsed > timeout:
            cam.release()
            cv2.destroyAllWindows()
            return None

    cam.release()
    cv2.destroyAllWindows()
    return save_path
