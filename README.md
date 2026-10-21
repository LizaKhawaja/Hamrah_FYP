# Hamrah 

Hamrah is a university-focused ride-sharing and carpooling application designed to help students coordinate rides in a convenient and organized way. The platform connects passengers with drivers and provides features for ride management, communication, and location tracking.

## Key Features

- **User Authentication:** Registration, login, and password recovery.
- **Ride Management:** Create ride offers, request rides, and manage ride bookings.
- **Driver & Passenger Profiles:** Separate interfaces and functionality for drivers and passengers.
- **Live Location Tracking:** Location-based services to support ride coordination and tracking.
- **In-App Communication:** Chat and calling functionality.
- **Face Verification:** Face-verification functionality for identity checks.
- **Notifications:** Notifications for relevant application events.
- **Vehicle Management:** Manage vehicle information.
- **Ratings & Reviews:** Rate drivers and passengers.
- **Emergency Support:** SOS-related functionality.

## Tech Stack

| Component | Technologies |
| --- | --- |
| Frontend | Flutter, Dart |
| Backend | Python, FastAPI |
| Database | PostgreSQL, SQLAlchemy |
| Authentication | JWT, OAuth2 |
| Real-Time Communication | WebSockets and calling services |
| Additional Integrations | Firebase, location services, AI-based features |

## Project Structure

```text
Hamrah_FYP/
├── hamrah-frontend/    # Flutter mobile application
│   ├── lib/
│   │   ├── screens/   # Application screens
│   │   ├── services/  # API and application services
│   │   ├── widgets/   # Reusable UI components
│   │   └── config/    # Application configuration
│   ├── android/
│   ├── ios/
│   └── pubspec.yaml
│
├── hamrah-backend/     # Python backend application
│   ├── app/
│   │   ├── routers/   # API endpoints
│   │   ├── services/  # Business logic and services
│   │   ├── models.py  # Database models
│   │   └── schemas.py # Data schemas
│   ├── alembic/       # Database migrations
│   ├── requirements.txt
│   └── README.md
│
└── README.md
```

## Getting Started

### Prerequisites

Install the following tools before running the project:

- Flutter SDK and Dart
- Python
- PostgreSQL
- Git

Additional credentials and service configurations may be required for Firebase, email, calling, and other integrated services.

### 1. Clone the Repository

```bash
git clone https://github.com/LizaKhawaja/Hamrah_FYP.git
cd Hamrah_FYP
```

### 2. Set Up the Backend

Open a terminal in the backend directory:

```bash
cd hamrah-backend
python -m venv venv
```

Activate the virtual environment.

**Windows PowerShell:**

```powershell
.\venv\Scripts\Activate.ps1
```

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

Configure the required environment variables using the provided `.env.example.conf` template. Set up PostgreSQL and configure the required database credentials and service settings.

For database-specific instructions, see [Backend PostgreSQL Setup](hamrah-backend/POSTGRES_SETUP.md).

Once the environment and database are configured, start the backend using the project's configured entry point. Check the [Backend README](hamrah-backend/README.md) for additional setup details.

### 3. Set Up the Frontend

Open another terminal:

```bash
cd hamrah-frontend
flutter pub get
flutter run
```

Configure the API base URL and required Firebase settings for your local environment before running the application.

## Configuration & Security

- Never commit `.env` files, passwords, private keys, or service-account credentials.
- Keep Firebase and other service credentials in their appropriate secure configuration files.
- Configure the backend URL for your own development or deployment environment.
- Some features require external services and valid credentials to work correctly.

## Project Purpose

Hamrah aims to make student carpooling more organized by bringing ride requests, driver coordination, communication, and related ride-management features into a single application.

## Repository

GitHub: [LizaKhawaja/Hamrah_FYP](https://github.com/LizaKhawaja/Hamrah_FYP)

---

**Hamrah — Connecting students through smarter ride-sharing.**
