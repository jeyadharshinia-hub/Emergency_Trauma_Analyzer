# Emergency Trauma Analyzer (ETA)

Doctor-focused trauma scan workflow app:
- Upload scan (`xray`, `ct`, `mri`)
- Run AI-assisted analysis
- Review/edit report
- Download PDF report
- Manage patients and open per-patient logs

Current app mode in this repo is **single doctor flow** with demo account.

## Stack
- Backend: Python, Flask, Flask-SQLAlchemy, OpenCV, ReportLab
- Frontend: React, Vite, Bootstrap
- Database: MySQL (default), SQLite (fallback option for local dev)
- AI: Gemini + Groq (with mock mode support)

## Prerequisites (Install First)
1. Python 3.11+ (3.12 recommended)
2. Node.js 20+ (npm included)
3. MySQL 8+ running locally (default path)

Check in PowerShell:

```powershell
python --version
node --version
npm --version
```

If you plan to run real AI (not mock), you also need:
- `GEMINI_API_KEY`
- `GROQ_API_KEY`

## Project Structure

```text
backend/
  app.py
  config.py
  models/
  routes/
  services/
  static/uploads/
  static/reports/
  assets/NotoSansTamil-Regular.ttf
frontend/
  src/
  vite.config.js
.env.example
```

## One-Time Setup

### 1) Clone and open folder

```powershell
git clone <your-repo-url>
cd "collage project-2"
```

### 2) Create `.env` from `.env.example`

```powershell
Copy-Item .env.example .env
```

### 3) Update `.env`

Minimum local defaults:

```env
DATABASE_URL=mysql+pymysql://root:root@127.0.0.1:3306/eta_db
SECRET_KEY=change-me-in-production
USE_MOCK_AI=true
AI_FAILOVER_TO_SAFE_MOCK=false
MAX_UPLOAD_MB=10
```

If using real AI:

```env
USE_MOCK_AI=false
GEMINI_API_KEY=PASTE_YOUR_GEMINI_API_KEY_HERE
GROQ_API_KEY=your_key
```

Gemini key replacement location:
- File: project root `.env`
- Replace this exact line:

```env
GEMINI_API_KEY=PASTE_YOUR_GEMINI_API_KEY_HERE
```

After updating the key, restart backend:

```powershell
cd backend
python app.py
```

### 4) Install backend dependencies

```powershell
python -m pip install -r backend/requirements.txt
```

### 5) Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

## Clean Development Run Guide

Run with **two terminals** from project root.

### Terminal 1: Backend

```powershell
cd backend
python app.py
```

Backend default URL:
- `http://127.0.0.1:5000`

### Terminal 2: Frontend

```powershell
cd frontend
npm run dev
```

Frontend default URL:
- `http://localhost:5173`

Vite proxies `/api` and `/static` to backend.

## First Login
- Doctor account
  - Username: `demo_doctor`
  - Password: `demo123`
  - Quick Access button logs in the demo doctor
- Admin account
  - Username: `admin`
  - Password: `admin123`
  - Use the new **Admin Quick Access** button on the login page or sign in directly; admins are redirected to `/admin` and can manage doctors, patients, and reports

## Quick Verification Checklist
1. Open `http://localhost:5173`
2. Login with demo doctor
3. Go to Upload page
4. Select/create patient, upload image, analyze
5. Open result page, save changes, download PDF
6. Go to Management, open Logs for a patient

Health check:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/api/health
```

## Database Modes

### Default (MySQL)
Use this in `.env`:

```env
DATABASE_URL=mysql+pymysql://root:root@127.0.0.1:3306/eta_db
```

Make sure:
- MySQL service is running
- Database exists (`eta_db`)
- Credentials in URL are correct

### Fallback (SQLite for local unblock)
If MySQL is unavailable, switch `.env`:

```env
DATABASE_URL=sqlite:///eta_dev.db
```

Notes:
- This works best when starting backend from `backend/` directory.
- For strict path control, you can use an absolute sqlite URL.

### Why can't I see the tables in MySQL?

The project does **not** ship with a static SQL dump—Flask-SQLAlchemy creates the tables automatically when you start the backend (`db.create_all()` is called inside `backend/app.py`). If you connect to MySQL and the tables are missing, it usually means one of the following:

- The `.env` `DATABASE_URL` is still pointing at SQLite (`sqlite:///eta_dev.db`) so the app never touched MySQL.
- The `eta_db` schema does not exist in MySQL yet. Create it manually before running the backend:

  ```sql
  CREATE DATABASE eta_db;
  -- (or use your preferred database name and update DATABASE_URL accordingly)
  ```

- Credentials/host/port in `DATABASE_URL` do not match your MySQL instance—double-check the values and restart the backend after editing `.env`.

Once the URL is correct and `backend/app.py` starts, you can verify the tables from a MySQL shell:

```sql
USE eta_db;
SHOW TABLES;
```

If you still see no tables, stop the backend, delete `backend/instance/eta_dev.db` (if it exists) to force the app to hit MySQL again, and then restart it. During development you can also fall back to the SQLite file (`backend/instance/eta_dev.db`) by pointing `DATABASE_URL` to it—this file already contains the seeded demo doctor/admin accounts.

## Production-Like Local Run (Optional)

Build frontend:

```powershell
cd frontend
npm run build
cd ..
```

Then run backend:

```powershell
cd backend
python app.py
```

Backend serves frontend from `frontend/dist` when build exists.

## Packaging for Deployment

A zipped copy of `frontend/dist` lives in `frontend-dist.zip` so you can share the latest static assets without rebuilding on every machine. After running `npm run build`, refresh the archive with something like `Compress-Archive -Path frontend/dist/* -DestinationPath frontend-dist.zip -Force` (or your preferred zip tool) so the client always gets matching production files.

## Git Ignore Safety (Before Push)

If `.gitignore` is accidentally changed/lost, restore these core entries:

```gitignore
__pycache__/
*.pyc
*.pyo
*.pyd
*.sqlite3
.env
.venv/
venv/
backend/.env
frontend/.env
node_modules/
frontend/node_modules/
frontend/dist/
backend/static/uploads/*
backend/static/reports/*
backend/instance/*
run-logs/
tmp/
!backend/static/uploads/.gitkeep
!backend/static/reports/.gitkeep
```

If ignored files were already tracked, re-apply ignore rules:

```powershell
git rm -r --cached .
git add .
git commit -m "fix: reapply gitignore rules"
```

This does not delete your local files from disk; it cleans Git index tracking.

## Common Issues

### MySQL connection refused
- Confirm MySQL service is running
- Confirm `DATABASE_URL` credentials/host/port
- Or switch to SQLite fallback

### Frontend cannot reach backend
- Confirm backend is running on port `5000`
- Confirm frontend is running on port `5173`

### Port already in use
Find listener:

```powershell
Get-NetTCPConnection -LocalPort 5000,5173 -State Listen
```

Stop process:

```powershell
Stop-Process -Id <PID> -Force
```

### AI errors
- Use `USE_MOCK_AI=true` for local testing without real AI keys
- For real AI, set valid `GEMINI_API_KEY` and `GROQ_API_KEY`

## Safety Disclaimer
`AI-assisted screening only. Final clinical decision must be made by a qualified doctor.`
