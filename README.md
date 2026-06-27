# Inven — Inventory & Ledger Dashboard

A full-stack web application for small-business inventory and financial management. Track stock levels, record cash and bank transactions, scan receipts with AI, and export reports — all from a responsive PWA dashboard.

**Live demo (static, mock API):** GitHub Pages deployment via `gh-pages.yml`  
**Production:** Azure Linux VM (Ubuntu) behind Nginx → Gunicorn on port 5000

---

## Features

### Inventory
- View and manage stock (ID, name, quantity, weighted average cost, min stock)
- **Restock** and **consume** with multi-line bills (single bill number, multiple items)
- Add items, manual stock overrides, delete items
- Full audit trail in `history` (RESTOCK, CONSUME, Dashboard Edit)
- Edit history records; delete with automatic stock reversal
- Supplier and consumer directories with searchable autocomplete
- Low-stock alerts on Overview (items below minimum threshold)
- Print stock and history reports

### Ledger
- Dual-account journal: **Cash** and **Bank**
- Cash IN / Cash OUT with merchant, description, and date
- Running balance per row (account balance + net balance)
- Self-transfer between Cash ↔ Bank (atomic paired entries)
- Period filters (all time, month, year, custom range)
- Ledger integrity check endpoint
- Merchant directory for autocomplete

### AI-assisted entry
- **Receipt scanner** — upload an image → extract amount, merchant, date (OpenRouter vision)
- **Text parser** — type natural language → pre-fill transaction form (OpenRouter text)
- Multi-model fallback chain; regex fallback when API key is missing (text only)
- FAB menu: Scan Receipt / Enter Manually → Stock IN or OUT

### Export & backup
- CSV export for inventory history and ledger
- Column-selectable print reports
- On-demand SQLite download (`GET /api/backup`)
- Daily automated backup to Google Drive (7-day retention)

### Real-time & PWA
- Socket.IO pushes live updates to connected clients (`inventory_updated`)
- Installable PWA (standalone, dark/light theme)
- Responsive desktop and mobile layouts

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Flask, Gunicorn |
| Real-time | Flask-SocketIO, gevent |
| Database | SQLite (`inventory.db`) |
| Auth | PyJWT (30-day sessions), Werkzeug password hashing |
| AI | OpenRouter API (multi-model fallback) |
| Frontend | React 18, Vite 5, lucide-react, socket.io-client |
| PWA | vite-plugin-pwa |
| CI/CD | GitHub Actions → Azure VM |
| Backup | Google Drive API |

---

## Architecture

```
Browser (React PWA + Socket.IO)
        │  HTTPS — /api/*, /socket.io
        ▼
Nginx (reverse proxy)
        ▼
Gunicorn + gevent → Flask (app.py)
        │
        ├── SQLite (inventory.db)
        ├── ledger_calculations.py (SQL window functions)
        ├── OpenRouter (receipt / text AI)
        └── Google Drive (daily backup)
```

Flask serves the pre-built React app from `frontend/dist` and exposes all business logic via REST APIs. Inventory and ledger are separate subsystems (restock does not auto-post to the cash ledger).

---

## Getting started

### Prerequisites

- Python 3.10+
- Node.js 18+ (Node 24 used in CI)

### Backend

```bash
# Clone and enter the repo
cd inven

# Python virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment
cp .env.example .env
# Edit .env — set FLASK_SECRET_KEY, DASHBOARD_PASSWORD, etc.

# Run (development)
python app.py
# Server: http://127.0.0.1:5000
```

On first run, `init_db()` creates all tables and seeds a default admin user from `ADMIN_USERNAME` / `DASHBOARD_PASSWORD`.

### Frontend

```bash
cd frontend
npm install
npm run dev
# Dev server: http://localhost:5173 (proxies /api to Flask)
```

For production, build static assets:

```bash
cd frontend
npm run build
# Output: frontend/dist — served by Flask
```

### Add dashboard users

```bash
python add_web_user.py
```

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | Yes | JWT signing secret |
| `DASHBOARD_PASSWORD` | Yes | Default admin password (first-run seed) |
| `ADMIN_USERNAME` | No | Default admin username (default: `Manager`) |
| `OPENAI_API_KEY` | No | OpenRouter API key for receipt/text AI |

See `.env.example` for a template.

---

## API overview

All protected routes require `Authorization: Bearer <token>`.

| Area | Endpoints |
|------|-----------|
| Auth | `POST /api/auth/login`, `POST /dashboard/login` |
| Inventory | `GET /api/inventory`, `POST /api/inventory/add`, `POST /api/inventory/update`, `POST /api/inventory/<id>/stock`, `DELETE /api/inventory/<id>` |
| History | `GET /api/history`, `PUT/DELETE /api/history/<id>` |
| Ledger | `GET /api/transactions`, `POST /api/transactions`, `PUT/DELETE /api/transactions/<id>`, `POST /api/transfer` |
| Summary | `GET /api/summary`, `GET /api/stats`, `GET /api/ledger/integrity` |
| Directories | `/api/suppliers`, `/api/consumers`, `/api/merchants` |
| AI | `POST /api/scan_receipt`, `POST /api/parse_text` |
| Ops | `GET /api/backup`, `GET /health` |

**WebSocket:** server emits `inventory_updated` on stock changes, transactions, transfers, and supplier deletes.

---

## Database

SQLite file: `inventory.db`

| Table | Purpose |
|-------|---------|
| `inventory` | Current stock, min stock, weighted avg price |
| `history` | Stock movement audit log |
| `ledger` | Cash IN/OUT journal (Cash / Bank accounts) |
| `suppliers` | Vendor directory |
| `consumers` | Buyer/site directory |
| `merchants` | Ledger merchant autocomplete |
| `web_users` | Dashboard login credentials |

**Restock pricing:** weighted average cost is recalculated on each restock when price > 0.

**Ledger balances:** computed via SQL window functions in `ledger_calculations.py`.

---

## Testing

Automated ledger integrity and API edge-case tests:

```bash
# Start the backend first
python app.py

# In another terminal
python tests/edge_case_tests.py
```

Covers amount validation, balance integrity (±₹0.01), self-transfer invariants, guarded deletes, and date edge cases.

---

## Deployment

### CI/CD (GitHub Actions)

**`deploy.yml`** — on push to `main`:
1. Build frontend (`npm run build`)
2. SCP `frontend/dist` to Azure VM
3. SSH: `git pull`, `pip install`, `systemctl restart sde_backend`

**`daily-backup.yml`** — midnight UTC cron:
- SSH to VM → run `backup_to_drive.py` → upload to Google Drive `SDE_Backup`

**`gh-pages.yml`** — static demo with mock API (no backend required)

### Production stack

- Azure Linux VM (Ubuntu)
- Nginx → Gunicorn (port 5000)
- systemd service: `sde_backend`
- Frontend served as static files by Flask

### Manual backup

```bash
python backup_to_drive.py   # Requires Google OAuth client_secrets.json on VM
```

Or download from the dashboard via the backup API endpoint.

---

## Project structure

```
├── app.py                    # Flask backend, routes, DB init, Socket.IO
├── ledger_calculations.py    # Ledger balance/summary SQL logic
├── requirements.txt
├── inventory.db              # SQLite (created at runtime)
├── add_web_user.py           # CLI to add dashboard users
├── backup_to_drive.py        # Google Drive backup script
├── tests/
│   └── edge_case_tests.py
├── .github/workflows/
│   ├── deploy.yml
│   ├── daily-backup.yml
│   └── gh-pages.yml
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── views/            # Overview, Inventory, Ledger, Export, Login
    │   ├── components/       # Modals, scanner, print, etc.
    │   └── utils/
    └── dist/                 # Production build (served by Flask)
```

---

## License

Private project — all rights reserved unless otherwise specified.
