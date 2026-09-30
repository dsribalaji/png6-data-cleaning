# Local Showcase Guide

Complete guide to running the PNG6 Agentic Data Cleaning Planner on your laptop for demonstration.

## Prerequisites

- **Python 3.12+** — [python.org](https://www.python.org/downloads/)
- **Node.js 24+** — [nodejs.org](https://nodejs.org/)
- **Groq API key** — Free at [console.groq.com](https://console.groq.com) (sign up, create API key)
- **Git**

Verify:
```bash
python --version  # 3.12+
node --version    # v24+
npm --version     # 10+
```

## Setup (15 minutes)

### 1. Clone the Repository
```bash
git clone https://github.com/dsribalaji/png6-data-cleaning.git
cd png6-data-cleaning
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:
```ini
# Database (SQLite for demo, no setup needed)
DATABASE_URL=sqlite+aiosqlite:///./planner.db

# Groq API (get free key from console.groq.com)
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-120b

# Demo mode: tasks run inline, no Redis needed
CELERY_TASK_ALWAYS_EAGER=true

# Local file storage
STORAGE_BACKEND=local
STORAGE_LOCAL_DIR=./storage
```

**Getting a Groq API key:**
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up (free, no credit card)
3. Go to "API Keys" → "Create API Key"
4. Copy the key (starts with `gsk_`)
5. Paste into `.env` as `GROQ_API_KEY`

### 4. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Create demo admin user
python scripts/seed_demo.py
```

Demo credentials:
- Email: `admin@example.com`
- Password: `Admin123!`

### 5. Start Backend (Terminal 1)

```bash
# Make sure .venv is activated
uvicorn planner.main:app --host 127.0.0.1 --port 8000
```

Verify: open http://127.0.0.1:8000/api/v1/health/live — should return `{"status":"ok"}`

API docs: http://127.0.0.1:8000/api/docs

### 6. Frontend Setup (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## Showcase Walkthrough (10 minutes)

### The Golden Workbook

Use the reference file: `data/reference/VendorInvoices_uncleaned.xlsx`

**What makes it messy:**
- 22 invoice rows × 14 columns (with 12 blank trailing rows)
- 313 nested line items buried in a JSON column
- 7 supplier name variants (e.g., "Microsoft Corporation (India) Private Limited" vs "Microsoft Corporation")
- 2 completely empty columns (customer_vat_number, shipping_addresses)
- Mixed formats, inconsistent values

**Expected results:**
- 22 rows, 14 columns profiled
- 17 inferred data quality rules
- 5-step cleaning plan
- 7 supplier variants → 5 canonical names
- Golden total: 154,292 (must be preserved)

### Step-by-Step Demo

1. **Login**
   - Open http://localhost:5173
   - Login with `admin@example.com` / `Admin123!`

2. **Upload**
   - Click "Upload Dataset"
   - Select `data/reference/VendorInvoices_uncleaned.xlsx`
   - Wait for ingest to complete (status: `ready_for_plan`)

3. **Profile** (automatic)
   - The system profiles the data: 22 rows, 14 columns
   - View column statistics, null counts, data types

4. **Infer Rules** (automatic)
   - 17 rules inferred, including:
     - "supplier_name has 7 variants that should be 5"
     - "customer_vat_number is 100% null"
     - "line_items contains nested JSON"

5. **Review Plan**
   - Click "Generate Plan"
   - 5 steps proposed:
     1. Drop `customer_vat_number` (all null)
     2. Drop `shipping_addresses` (all null)
     3. Standardize `supplier_name` (7 → 5 variants)
     4. Expand `line_items` (313 nested records)
     5. Drop `total_price` (derived, can be recalculated)
   - Each step shows estimated data loss

6. **Approve**
   - Review each step
   - Accept, edit, or reject
   - Click "Approve Plan"

7. **Execute & Validate**
   - Approved steps run deterministically
   - Validation tests check results
   - Export the cleaned workbook

8. **Rollback** (if needed)
   - Restore the original file byte-for-byte
   - Verify SHA-256 hash matches

## Troubleshooting

### "GROQ_API_KEY not set"
- Make sure `.env` exists in `backend/` directory
- Verify the key starts with `gsk_`
- Restart the backend after changing `.env`

### "Database locked" (SQLite)
- Only one process should write to SQLite at a time
- If using eager mode, this is normal — tasks run inline

### "Port 8000 already in use"
```bash
# Find and kill the process
lsof -ti:8000 | xargs kill -9  # macOS/Linux
# Windows: netstat -ano | findstr :8000, then taskkill /PID <pid> /F
```

### "Port 5173 already in use"
- Vite will ask to use a different port — say yes
- Or: `npm run dev -- --port 5174`

### Frontend can't reach backend
- Verify backend is running on port 8000
- Check `frontend/.env` or `vite.config.ts` for API URL
- Default: `http://127.0.0.1:8000`

## Production Mode (Docker)

For a production-like setup with PostgreSQL, Redis, and S3-compatible storage:

```bash
docker compose up --build
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- MinIO (port 9000, S3-compatible storage)
- Backend API (port 8000)
- Frontend (port 5173)
- Celery workers

Set in `.env`:
```ini
DATABASE_URL=postgresql+asyncpg://planner:planner@db:5432/planner
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_TASK_ALWAYS_EAGER=false
STORAGE_BACKEND=s3
```

## What the AI Does (and Doesn't Do)

**The AI (Groq) DOES:**
- Suggest data quality rules ("these 7 names look like 5 entities")
- Propose cleaning operations from a fixed catalogue
- Help explain the plan in plain language

**The AI DOES NOT:**
- Generate or execute code (all transformations are pre-built, deterministic functions)
- Make final decisions (human approves every step)
- Touch the data directly (it only suggests, the engine executes)

This is by design — the system is auditable and safe because the AI is an advisor, not an actor.
