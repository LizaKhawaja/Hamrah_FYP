from app.face_verification.service import extract_face, compare_faces

ID_IMAGE = "test_id2.jpg"
LIVE_IMAGE = "test_live.jpeg"

id_face = extract_face(ID_IMAGE, "id")
live_face = extract_face(LIVE_IMAGE, "live")

if id_face is None or live_face is None:
    print("Face not extracted")
else:
    match, distance = compare_faces(id_face, live_face)
    print("MATCH:", match)
    print("DISTANCE:", distance)
