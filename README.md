# Astrology Web App (Flask + SQLite + Tailwind)

A complete beginner-friendly astrology app with strict multi-step validation, optional palm-reading simulation, AI-style predictions, and PDF download support.

## Project Structure

```text
astrology_app/
├── app.py
├── requirements.txt
├── README.md
├── instance/
│   └── astrology.db                # auto-created
├── uploads/                        # uploaded palm images
├── templates/
│   └── index.html
└── static/
    ├── css/
    │   └── styles.css
    └── js/
        └── app.js
```

## Features Implemented

- Strict required fields:
  - Full Name
  - Date of Birth
  - Time of Birth
  - Place of Birth
- Step-by-step flow:
  1. Birth details
  2. Ask: "Do you want more accurate prediction using palm reading?"
  3. Optional palm upload flow
  4. Processing + results
- Astrology engine:
  - Zodiac sign
  - Moon sign (approximate)
  - Ascendant (approximate)
  - Rule-based personality, career, love, and future insights
- Optional palm analysis:
  - Simulated logic (no ML model required)
  - Optional hand choice + image upload
- AI-style report sections:
  - Personality Analysis
  - Career Path
  - Love & Relationships
  - Future Outlook
- UI/UX:
  - Dark mystical gradient
  - Glow effects
  - Animated loader + fake progress bar
- Result actions:
  - Download as PDF (browser print-to-PDF)
  - Try again

## Run Locally

### 1) Open terminal in project folder

```bash
cd astrology_app
```

### 2) Create and activate virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Start app

```bash
python app.py
```

### 5) Open browser

Go to:

`http://127.0.0.1:5000`

## Notes

- SQLite DB is created automatically in `instance/astrology.db`.
- Uploaded images are saved in `uploads/`.
- "Download as PDF" uses your browser print dialog.
