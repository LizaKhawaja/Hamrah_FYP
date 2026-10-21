# FYP Backend (FastAPI + Postgres)

This repository contains a **FastAPI** backend for a ride-sharing style app with:

- **Auth** (JWT login)
- **Users** (passenger + driver signup, OTP verification)
- **Rides** (driver posts rides, driver lists own rides)
- **Ride Requests** (passenger searches rides + requests/auto-books)
- **Face verification** (YOLO `best.pt` + DeepFace/ArcFace, webcam capture supported)

---

## Prerequisites

- **Python 3.10+** (recommended)
- **PostgreSQL** (local or remote)
- On Windows, for face verification:
  - A working **webcam** (if you use the endpoint that captures a live image)
  - OpenCV dependencies are included via `opencv-python` in `requirements.txt`

---

## Setup (Windows PowerShell)

From the repo root (`D:\fyp`):

```powershell
# 1) Create & activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2) Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Configure environment variables (`.env`)

This project loads settings from a `.env` file (see `app/config.py`).

Create a file named `.env` in the repo root with **these keys**:

```env
# Postgres
DATABASE_HOSTNAME=localhost
DATABASE_PORT=5432
DATABASE_NAME=your_db_name
DATABASE_USERNAME=postgres
DATABASE_PASSWORD=your_password

# JWT
SECRET_KEY=change_me_to_a_long_random_string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Notes:
- The app will connect using:
  - `postgresql://DATABASE_USERNAME:DATABASE_PASSWORD@DATABASE_HOSTNAME:DATABASE_PORT/DATABASE_NAME`
- Keep `.env` private. It is already ignored by `.gitignore`.

---

## Database initialization

On startup, the app runs `models.Base.metadata.create_all(bind=engine)` (see `app/main.py`),
so tables are created automatically **if the database exists and credentials are correct**.

### Create the database (example)

Create the Postgres database named in `DATABASE_NAME` (one-time step). Example with `psql`:

```sql
CREATE DATABASE your_db_name;
```

### Seed `dsu_students` (required for signup)

Passenger/driver signup validates the DSU Registration ID against the `dsu_students` table.
If this table is empty, signup will fail with “Invalid DSU Registration ID”.

If you have `students.csv` in the repo root, you can import it using Postgres `COPY`.

1) Ensure the CSV has columns that match:
   - `full_name`
   - `dsu_reg_id`
   - `department` (optional)

2) Import example (run inside `psql`):

```sql
-- Adjust the absolute path if needed.
-- On Windows, you may need to escape backslashes or use forward slashes.
COPY dsu_students(full_name, dsu_reg_id, department)
FROM 'D:/fyp/students.csv'
DELIMITER ','
CSV HEADER;
```

---

## Run the API server

From the repo root:

```powershell
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open:
- Interactive API docs (Swagger UI): `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

---

## Key API endpoints (high level)

### Authentication

- `POST /login` (form-data: `username` = DSU reg ID, `password`)
  - Returns a Bearer JWT token.

### Users

- `POST /users/passenger` (JSON)
- `POST /users/driver` (multipart form fields; downloads CNIC/live images from URLs and verifies faces)
- `POST /users/verify-otp` (JSON)
- `POST /users/resend-otp` (JSON)

### Rides

- `POST /rides/` (driver only; requires Bearer token)
- `GET /rides/my` (driver only; requires Bearer token)

### Ride requests

- `GET /ride_requests/search` (passenger only; requires Bearer token)
- `POST /ride_requests/` (passenger only; requires Bearer token)

---

## Face verification notes

Face verification uses:

- **YOLO** (Ultralytics) to extract faces using a model file named `best.pt`
- **DeepFace (ArcFace)** to compare extracted faces

### `best.pt` is required

The face extraction code searches for `best.pt` in these locations:

- `best.pt`
- `Main/best.pt`
- `beta-testing/best.pt`

If it cannot find the model, face verification will raise: `FileNotFoundError("YOLO model (best.pt) not found")`.

### Webcam capture endpoint

`POST /face-verification/verify-cnic` uploads a CNIC image and then opens the **webcam** to capture a live image automatically.
This requires a GUI-capable environment and a working camera.

---

## Troubleshooting

- **DB connection errors**
  - Verify Postgres is running and `.env` credentials are correct.
  - Ensure the database in `DATABASE_NAME` exists.
- **Signup always fails**
  - Import DSU students into `dsu_students` (see seeding section).
- **Face verification fails**
  - Ensure `best.pt` exists in the repo root.
  - Make sure images contain a clear, front-facing face.
  - Webcam endpoint needs camera access and may fail on headless/remote setups.

