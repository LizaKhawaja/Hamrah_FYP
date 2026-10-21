# PostgreSQL Setup Guide for Hamrah Backend

This guide explains how to set up PostgreSQL for the Hamrah FastAPI backend.

## Prerequisites

- Python 3.9+
- PostgreSQL 13+ installed locally OR a cloud PostgreSQL instance (Supabase, Neon, Railway, etc.)

## Option 1: Local PostgreSQL Setup (Windows)

### Step 1: Install PostgreSQL

Download and install PostgreSQL from [postgresql.org](https://www.postgresql.org/download/windows/).

During installation:
- Remember the password you set for the `postgres` superuser
- Default port is `5432`
- Keep default locale

### Step 2: Create the Database

Open **pgAdmin** (installed with PostgreSQL) or use **psql** command line:

```sql
-- Connect as postgres superuser, then run:
CREATE DATABASE hamrah_db;
CREATE USER hamrah_user WITH ENCRYPTED PASSWORD 'your_password_here';
GRANT ALL PRIVILEGES ON DATABASE hamrah_db TO hamrah_user;
GRANT ALL ON SCHEMA public TO hamrah_user;
```

### Step 3: Configure Environment Variables

Create/edit `.env` file in `hamrah-backend-main/` directory:

```env
# Database (PostgreSQL)
DATABASE_URL=postgresql+psycopg2://hamrah_user:your_password_here@localhost:5432/hamrah_db
DATABASE_HOSTNAME=localhost
DATABASE_PORT=5432
DATABASE_USERNAME=hamrah_user
DATABASE_PASSWORD=your_password_here
DATABASE_NAME=hamrah_db

# If you want to use SQLite instead for testing:
# USE_SQLITE=True
# SQLITE_PATH=hamrah_test.db

# JWT / Auth
SECRET_KEY=your-super-secret-key-change-me-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Email (Gmail example)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password

# Agora
AGORA_APP_ID=your-agora-app-id
AGORA_APP_CERTIFICATE=your-agora-certificate

# SOS Numbers
SOS_POLICE_NUMBER=15
SOS_HAMRAH_SUPPORT_NUMBER=+92-300-1234567
SOS_CAMPUS_SECURITY_NUMBER=+92-21-1234567
```

### Step 4: Install Python Dependencies

```bash
cd hamrah-backend-main
pip install psycopg2-binary
# OR if using requirements.txt:
pip install -r requirements.txt
```

### Step 5: Run Database Migrations

The project uses SQLAlchemy with auto-create. Just start the server and tables will be created:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Tables are automatically created on first run via `Base.metadata.create_all()`.

---

## Option 2: Cloud PostgreSQL (Supabase - FREE)

### Step 1: Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign up
2. Create a new project (free tier available)
3. Wait for the database to provision (~2 minutes)

### Step 2: Get Connection String

1. Go to **Project Settings** → **Database**
2. Find **Connection string** → **URI** tab
3. Copy the connection string (it looks like):
   ```
   postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:6543/postgres
   ```
4. Convert it to SQLAlchemy format:
   ```
   postgresql+psycopg2://postgres.xxxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:6543/postgres
   ```

### Step 3: Update `.env`

```env
DATABASE_URL=postgresql+psycopg2://postgres.xxxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:6543/postgres
```

---

## Option 3: Cloud PostgreSQL (Neon - FREE)

### Step 1: Create Neon Project

1. Go to [neon.tech](https://neon.tech) and sign up
2. Create a new project
3. Copy the connection string from the dashboard

### Step 2: Update `.env`

```env
DATABASE_URL=postgresql+psycopg2://username:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
```

---

## Verification

After setup, test the connection:

```bash
# Windows PowerShell
cd hamrah-backend-main
python -c "from app.database import engine; print('Connected!' if engine else 'Failed')"
```

Or start the server and check for database errors:

```bash
uvicorn app.main:app --reload
```

If you see `Application startup complete` without database errors, you're good to go!

---

## Common Issues

### Issue 1: `psycopg2` not found
**Fix:** `pip install psycopg2-binary`

### Issue 2: `password authentication failed`
**Fix:** Check your `.env` file credentials match what you set in PostgreSQL.

### Issue 3: `could not connect to server`
**Fix:** 
- Make sure PostgreSQL service is running
- Check `DATABASE_HOSTNAME` and `DATABASE_PORT`
- For cloud DBs, check if your IP is whitelisted

### Issue 4: `relation does not exist`
**Fix:** Tables aren't created yet. Restart the server — `Base.metadata.create_all()` runs on startup.

### Issue 5: SSL Required (cloud DBs)
**Fix:** Add `?sslmode=require` to the end of your DATABASE_URL.

---

## Database Schema

Tables auto-created on first run:
- `users` - User accounts (passengers, drivers, admins)
- `vehicles` - Driver vehicles
- `rides` - Posted rides
- `ride_requests` - Passenger requests to join rides
- `ratings` - Driver ratings by passengers
- `passenger_ratings` - Passenger ratings by drivers
- `device_tokens` - Push notification tokens
- `chat_messages` - In-app chat
- `sos_contacts` - Emergency contacts
- `face_verifications` - CNIC/Face verification records

---

## Useful Commands

```bash
# Connect to local PostgreSQL
psql -U postgres -d hamrah_db

# List all tables
\dt

# View a table's structure
\d rides

# Check ride_requests status
SELECT id, ride_id, passenger_id, status, created_at FROM ride_requests ORDER BY created_at DESC LIMIT 10;

# Check unrated rides for a passenger
SELECT r.id, r.status, rr.passenger_id, rr.status as req_status
FROM rides r
JOIN ride_requests rr ON rr.ride_id = r.id
WHERE rr.passenger_id = 5
AND (r.status = 'completed' OR rr.status IN ('dropped', 'completed'))
AND NOT EXISTS (
  SELECT 1 FROM ratings WHERE ride_id = r.id AND passenger_id = rr.passenger_id
);
```

---

## Migration to PostgreSQL from SQLite

If you have data in SQLite and want to migrate:

1. Export data from SQLite:
```bash
sqlite3 hamrah_test.db .dump > dump.sql
```

2. Use a tool like `pgloader` or write a custom Python script using SQLAlchemy:

```python
from sqlalchemy import create_engine
import pandas as pd

# Read from SQLite
sqlite_engine = create_engine('sqlite:///hamrah_test.db')
df = pd.read_sql('SELECT * FROM users', sqlite_engine)

# Write to PostgreSQL
pg_engine = create_engine('postgresql+psycopg2://user:pass@localhost/hamrah_db')
df.to_sql('users', pg_engine, if_exists='append', index=False)
```

---

## Support

If you face issues, check:
- `.env` file has all required variables
- PostgreSQL service is running (local) or accessible (cloud)
- Firewall allows connection on port 5432
- Database user has proper permissions
