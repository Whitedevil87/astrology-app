# Celestial Arc — Production-Ready Vedic Astrology App

A highly scalable, production-grade Vedic astrology application featuring exact astronomical ephemeris calculations (Swiss Ephemeris), user authentication, AI-augmented readings, and dual-database support.

##  Enterprise Features

- **Robust Architecture:** Modular Flask Blueprints with distinct separation of concerns (Auth, Services, Analysis, AI).
- **Production Infrastructure:** Designed for deployment on PaaS (Render, Heroku) using `gunicorn` with dynamic thread workers.
- **Dual Database Strategy:** 
  - Uses **PostgreSQL (Supabase)** for production scalability.
  - Automatically falls back to local **SQLite** for zero-config local development.
- **Security First:** 
  - **Upstash Redis** powered rate-limiting to prevent API abuse.
  - **JWT Authentication** (via Supabase Auth) with secure HTTP-only configurations.
  - UUIDs for all public records to prevent enumeration attacks.
- **Advanced Astrology Engine:**
  - Integrates `pyswisseph` for exact sidereal planetary positions, Vimshottari Dasha calculations, and precise Lagna matching.
  - Hybrid AI synthesis utilizing OpenAI/Groq for nuanced, personalized user readings.

## Project Structure

```text
astrology_app/
├── app.py                      # Application entry point and app factory
├── blueprints/                 # Flask modular routes
│   ├── auth.py                 # JWT, Login, Registration routes
│   └── compatibility.py        # Synastry and Guna Milan endpoints
├── services/                   # Core business logic
│   ├── analysis_service.py     # Astrology data aggregation
│   ├── auth_service.py         # Supabase Auth wrapper & decorators
│   ├── scheduler_service.py    # Background cron jobs (Horoscopes)
│   └── storage_service.py      # Cloud storage wrapper
├── utils/                      # Shared utility modules
│   ├── geo.py                  # Geocoding & Timezone resolution
│   ├── astrology_math.py       # Core astronomical math functions
│   ├── ai_client.py            # LLM API orchestrator
│   └── vedic_engine.py         # Vedic calculation orchestrator
├── vedic/                      # Deep astronomical engine
│   ├── swisseph_engine.py      # High-precision Swiss Ephemeris wrapper
│   ├── transits.py             # Planetary transit calculator
│   └── vargas.py               # Divisional chart (Navamsha) logic
├── tests/                      # Unit and integration tests
├── scripts/                    # Developer scripts and migrations
├── templates/                  # Server-side HTML templates (Landing, Auth)
└── static/                     # Tailwind CSS and vanilla JS modules
```

##  Run Locally

### 1. Create a virtual environment
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\Activate.ps1
# On Mac/Linux:
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the example config and adjust as needed:
```bash
cp .env.example .env
```
*(Note: If no `.env` variables are set, the app gracefully falls back to local SQLite and in-memory rate limiting for instant development).*

### 4. Start the Application
```bash
# Start development server
flask run

# Or start with Gunicorn (Production simulation)
gunicorn -c gunicorn.conf.py wsgi:app
```

## Production Deployment

This repository is pre-configured for instant deployment to Render or Heroku.
1. Connect your GitHub repository to your platform.
2. The platform will automatically detect the `Procfile` and `requirements.txt`.
3. Set the following required environment variables in your platform dashboard:
   - `DATABASE_URL` (PostgreSQL connection string)
   - `SUPABASE_URL` & `SUPABASE_SERVICE_ROLE_KEY`
   - `UPSTASH_REDIS_REST_URL` & `UPSTASH_REDIS_REST_TOKEN`
   - `OPENAI_API_KEY` (or `GROQ_API_KEY`)

## License
This project is licensed under the MIT License - see the `LICENSE` file for details.
