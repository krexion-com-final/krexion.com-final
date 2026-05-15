# Krexion — Production Admin Guide

> Yeh guide aap (business owner / admin) ke liye hai. Krexion ko production mein
> properly manage karne ke liye sab kuch yahan hai.

[Comprehensive Urdu + English production admin guide]

---

# 🎯 Admin Role — Aap Kya Kar Sakte Hain

Aap (Krexion admin) yeh sab kar sakte hain:
- 🔐 **User Management** — naye users approve / reject / suspend karna
- 🎫 **License Management** — keys issue, extend, revoke, delete karna
- 💰 **Pricing & Trial Rules** — monthly price, trial days, max PCs configure
- 📊 **Analytics Dashboard** — sare users ki activity dekhna
- 🚦 **Feature Gating** — kaunse user kaunsi features access kar sake
- 🌐 **Global Kill Switch** — emergency mein sab installs band karna
- 🔒 **Sub-user Management** — multi-tenant accounts

---

# 🚀 Setup — Aap Ka Admin Panel Kahan Chalaye

## Option A — Local PC (Quick start, free)

Apne PC pe `Krexion-EASY-INSTALL.bat` se install karein. Customer install ki tarah hi.

Admin panel: `http://localhost:3000/admin-login`

**Limitation**: PC band hone pe admin offline. Customers prabhavit nahi hote (license heartbeat observe-only mode mein hai).

## Option B — Mobile Access Via Tunnel (Best for daily use)

Aap PC pe admin panel chala kar mobile se globally access karna chahte hain:

1. PC pe Krexion chal raha ho
2. **`ADMIN-GO-ONLINE.bat`** double-click karein (admin only, regular `GO-ONLINE.bat` se different)
3. Beautiful purple/magenta page khulegi:
   - 🌐 Public URL (auto-deep-linked to `/admin-login`)
   - 🔑 Admin credentials (ADMIN_EMAIL + ADMIN_PASSWORD from .env, one-click copy)
   - 📱 QR code
4. Mobile se URL kholein → admin panel mobile pe

⚠️ **NEVER share `ADMIN-GO-ONLINE.bat` with customers!** Yeh sirf admin's mobile access ke liye hai. Customers ke liye `GO-ONLINE.bat` use karein.

## Option C — Permanent Cloud Hosting (Best for production / serious business)

Render.com pe deploy karein — Emergent / local PC se completely independent:

### Setup (15 min, one-time):

1. **MongoDB Atlas signup**: https://cloud.mongodb.com → M0 (free) cluster → connection string note karein

2. **Render.com signup with GitHub**: https://render.com → "Sign up with GitHub"

3. **New Blueprint Instance**:
   - "New +" → "Blueprint"
   - Select `ronaldsexedwards40-glitch/dynabook` repo
   - Render automatically `render.yaml` detect karega
   - `MONGO_URL` env variable mein apni Atlas connection string paste karein
   - "Apply" click karein

4. **15-20 min wait** → 3 services deploy honge:
   - `krexion-backend` (Docker FastAPI)
   - `krexion-frontend` (static React)
   - Aap ka permanent URL: `https://krexion-frontend-XXXX.onrender.com`

5. **Update DNS** (optional, $10/year):
   - Own domain (e.g., krexion.com) kharidein
   - Render → frontend service → Settings → Custom Domain → add
   - DNS A record → Render's IP

6. ✅ **Done!** Admin panel ab 24/7 available. Git push se auto-deploy.

### Cost summary:

| Use Case | Cost | What you get |
|----------|------|--------------|
| Free tier | $0/mo | 24/7 access, 30 sec cold start when idle |
| Starter | $7/mo | Always-on, no cold start |
| Own domain | $10/year | krexion.com instead of onrender.com |
| MongoDB Atlas M0 | Free | 512 MB DB, enough for 1000+ users |

📖 **Full guide**: `ADMIN-URL-SETUP.md` (15 min walkthrough)

---

# 🔐 User Management

## New User Approval Flow

1. Customer signs up → user created with `status=pending`
2. Customer dekhe ga "Account pending admin approval" message
3. **Aap admin panel mein**:
   - Sidebar → **Users** ya **Admin Dashboard**
   - Pending users list dekhein
   - **Approve** button → `status=active`, default features assign
4. Customer ko email notification (agar Resend configured hai)
5. Customer login kar sakta hai

## Available API Endpoints (Admin only — JWT required)

```bash
# Login (get JWT)
curl -X POST http://YOUR-URL/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@krexion.local","password":"admin123"}'

# Returns: { "access_token": "eyJ...", "is_admin": true }
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/users` | GET | List all users (paginated) |
| `/api/admin/users/{id}` | GET | Get single user details |
| `/api/admin/users/{id}` | PUT | Update user (status, features, etc) |
| `/api/admin/users/{id}` | DELETE | Delete user |
| `/api/admin/users/{id}/suspend` | POST | Suspend user |
| `/api/admin/users/{id}/activate` | POST | Reactivate suspended user |

## Feature Gating

User ko features control karne ke liye PUT request karein:

```bash
curl -X PUT http://YOUR-URL/api/admin/users/{user_id} \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "active",
    "features": {
      "links": true,
      "rut": true,
      "form_filler": true,
      "cpi": false,
      "email_checker": true
    }
  }'
```

---

# 🎫 License Management

## Admin License Panel

URL: `http://YOUR-URL/admin/licenses`

Yahan 2 tabs hain:

### Tab 1: Pricing & Rules

Configure karein:
- 💰 **Monthly Price** (e.g., $9.99)
- 💱 **Currency** (USD, EUR, INR, etc.)
- 🆓 **Trial Days** (default 7)
- 💻 **Max PCs per License** (default 1)
- 🚦 **Master Switch** (ON / OFF — system-wide kill switch)
- 📧 **Admin Contact Email** (for manual purchase requests)
- 💬 **Admin Contact Message** (instructions for customers to pay)

### Tab 2: Customers / Licenses

Pura license list with:
- **Search** by email / key / status
- **Filter** by status (active, trial, expired, revoked)
- **Per-row actions**: Extend / Revoke / Delete
- **Manual Issue** button (top right) — direct issue license to customer

## Available API Endpoints

### Public (used by installer):
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/license/config` | GET | Live pricing/rules (for installer UI) |
| `/api/license/start-trial` | POST | Start free trial |
| `/api/license/activate` | POST | Bind license to 1 PC |
| `/api/license/validate` | POST | Heartbeat check (every 6h) |

### Admin (JWT required):
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/admin/license/config` | GET/PUT | Edit pricing/rules globally |
| `/api/admin/license/list` | GET | Paginated, searchable license list |
| `/api/admin/license/issue?email=&days=` | POST | Manually issue license |
| `/api/admin/license/extend/{key}?days=` | POST | Extend expiry |
| `/api/admin/license/revoke/{key}` | POST | Block customer's PC instantly |
| `/api/admin/license/{key}` | DELETE | Permanently delete single license |
| `/api/admin/license/bulk-delete` | POST | Bulk delete by filter |
| `/api/admin/license/cleanup` | POST | Delete all revoked + expired |

## Manual Purchase Flow

Stripe removed, all purchases manual:

1. Customer setup wizard → **"Contact Admin to Buy a License"** click karta hai
2. Customer ka default email client khulta hai pre-filled subject "License Purchase Request — Krexion" ke saath
3. Aap (admin) ko email milti hai with customer's PC name + details
4. Aap customer se payment lete hain (crypto, bank, cash — off-app)
5. Admin panel khol kar `/admin/licenses` → **"Issue manual license"** button
6. Email + days daalein → **Issue** click
7. License key generate ho jati hai → customer ko send karein (WhatsApp / email)
8. Customer setup wizard → "I have a license key" → paste → Activate
9. ✅ Done — customer's PC pe Krexion chal jaye ga

## Bulk Cleanup

Purane licenses delete karne ke liye:
- 🗑️ **Delete Revoked + Expired** — one-click cleanup
- 🗑️ **Delete all Revoked** — sirf revoked
- 🗑️ **Delete all Trial** — sirf trial keys

⚠️ Safety: Active licenses **kabhi delete nahi hote** automated cleanup mein.

---

# 🚦 Global Kill Switch (Emergency)

Aap ki licenses leak ho gayi? Foran action:

## Method 1: Master Switch via Admin Panel
1. `/admin/licenses` → Pricing & Rules tab
2. **"Master Switch"** toggle OFF
3. Save → 30 second mein sare installers fail honge

## Method 2: Per-license Revoke
Selected customers ko block karein:
1. `/admin/licenses` → Customers tab
2. Search by email
3. **Revoke** button → confirm

## Method 3: Installer-level Kill (GitHub edit)
Even un PCs ko block karein jo abhi install karne ki koshish kar rahe hain:
1. GitHub repo → `.installer-status` file
2. Edit → `REVOKED` likhein → commit
3. 30 sec mein worldwide installers fail Layer-3 pe

📖 Detailed steps: `ADMIN-GUIDE-URDU.md` mein hain (3 use cases ke saath)

---

# 📊 Analytics & Monitoring

## Health Endpoints (No auth)
```bash
# Overall health
curl http://YOUR-URL/api/diagnostics/health

# Hardware profile (auto-tuning info)
curl http://YOUR-URL/api/diagnostics/hardware-profile
```

## Logs (Aap ki PC pe)
```powershell
# Windows
cd C:\krexion
.\KREXION-LOGS.bat

# Linux/macOS
cd /opt/krexion
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f mongo
```

## Database Access
```powershell
# Local mongo shell
docker exec -it krexion-mongo mongosh

# Or via Compass (GUI):
# Connection: mongodb://localhost:27017
```

---

# 🔧 Configuration

## Main .env Variables

`C:\krexion\.env` (Windows) or `/opt/krexion/.env` (Linux):

| Variable | Purpose | Default |
|----------|---------|---------|
| `MONGO_URL` | MongoDB connection | `mongodb://localhost:27017` |
| `DB_NAME` | Database name | `krexion` |
| `JWT_SECRET_KEY` | Auth token signing | (random 32-char) |
| `ADMIN_EMAIL` | Admin login email | `admin@krexion.local` |
| `ADMIN_PASSWORD` | Admin login password | (random 16-char) |
| `POSTBACK_TOKEN` | Affiliate postback auth | (random) |
| `RUT_MAX_CONCURRENCY` | Max RUT workers (hard cap) | auto-tuned |
| `RUT_MEM_LIMIT_MB` | RUT memory cap | auto-tuned |
| `CORS_ORIGINS` | CORS allowed origins | `*` |
| `RESEND_API_KEY` | (optional) Email sending | empty |
| `GOOGLE_SHEETS_SA_PATH` | (optional) GSheet live-delete | empty |
| `LICENSE_SERVER_URL` | (optional) Remote license server | empty |
| `LICENSE_KEY` | (optional) Customer's key (auto-set by installer) | empty |

## Resend Email Setup (Optional)

Customer activation/payment emails ke liye:
1. https://resend.com signup → free 100/day
2. API key copy
3. `.env` mein add: `RESEND_API_KEY=re_xxxxx`
4. `SMTP_FROM=admin@yourdomain.com` add karein
5. `docker compose restart backend`

## Google Sheets Integration (Optional)

Live row-delete from Google Sheets:
1. Google Cloud Console → Service Account banaye
2. JSON download → `/app/backend/secrets/gsheets-sa.json` pe save
3. `.env` mein: `GOOGLE_SHEETS_SA_PATH=/app/backend/secrets/gsheets-sa.json`
4. Sheet share with SA email
5. `docker compose restart backend`

---

# 🔄 Updates & Backups

## Update Krexion
```powershell
cd C:\krexion
.\KREXION-UPDATE.bat
# Auto-backup mongo before pull
```

```bash
cd /opt/krexion
git pull
docker compose up -d --build
```

## Manual Backup
```bash
# Backup mongo
docker exec krexion-mongo mongodump --out /backup/$(date +%Y%m%d)
# Copy to host
docker cp krexion-mongo:/backup/$(date +%Y%m%d) ./backup-$(date +%Y%m%d)

# Backup uploads
cp -r ./backend/uploaded_resources ./backup-uploads-$(date +%Y%m%d)
```

## Restore Backup
```bash
docker cp ./backup-20260514 krexion-mongo:/restore
docker exec krexion-mongo mongorestore /restore
```

---

# 🆘 Troubleshooting

## Problem: Admin panel 500 error
```bash
docker compose logs backend | tail -100
# Check for ImportError, OperationalError, etc.
```

## Problem: Customer can't login after approval
- Verify user `status=active` in MongoDB
- Check `features` array — at least one feature must be true
- Check JWT_SECRET_KEY same on backend (not changed after token issued)

## Problem: License keys not generating
- Check `license_config` collection in MongoDB
- Verify admin JWT not expired
- Check backend logs for stack trace

## Problem: Mongo running out of disk
```bash
docker exec krexion-mongo mongosh --eval "db.runCommand({compact:'real_user_traffic_results'})"
# Or delete old jobs:
docker exec krexion-mongo mongosh krexion --eval "
  db.real_user_traffic_jobs.deleteMany({
    status: 'completed',
    completed_at: { \$lt: new Date(Date.now() - 30*24*60*60*1000) }
  })
"
```

## Problem: Want to reset admin password
```powershell
# Edit .env
notepad C:\krexion\.env
# Change ADMIN_PASSWORD line
# Restart:
docker compose restart backend
```

---

# 📈 Production Best Practices

### ✅ Do
- [x] Strong JWT_SECRET_KEY (32+ random chars)
- [x] Strong ADMIN_PASSWORD (changed from default)
- [x] CORS_ORIGINS locked to your domain (not `*`)
- [x] HTTPS via Cloudflare Tunnel or Render's auto-SSL
- [x] Daily mongo backups (cron job)
- [x] Resend API key configured for emails
- [x] Monitor `/api/diagnostics/health` (uptime monitoring)
- [x] Bulk cleanup expired licenses monthly

### ❌ Don't
- [ ] Default `admin123` password (CHANGE IMMEDIATELY)
- [ ] CORS_ORIGINS=`*` in production
- [ ] Share `ADMIN-GO-ONLINE.bat` with customers
- [ ] Commit `.env` to git (already in `.gitignore`)
- [ ] Run as root (use dedicated user)

---

# 🎯 Quick Reference

## Default URLs
```
Frontend:        http://localhost:3000
Admin Login:     http://localhost:3000/admin-login
Admin License:   http://localhost:3000/admin/licenses
Admin Dashboard: http://localhost:3000/admin/dashboard
Backend API:     http://localhost:8001
API Docs:        http://localhost:8001/docs
Health:          http://localhost:8001/api/diagnostics/health
```

## Default Credentials (CHANGE!)
```
Email:    admin@krexion.local
Password: admin123 (or from .env)
```

## Quick Commands
```powershell
# Status
docker compose ps

# Logs
docker compose logs -f

# Restart everything
docker compose restart

# Update + restart
git pull && docker compose up -d --build

# Backup mongo
docker exec krexion-mongo mongodump --out /tmp/backup
```

---

# 🆘 Need Help?

- 📖 User installation guide: `USER-GUIDE-PRODUCTION.md`
- 📖 Detailed admin guide (Urdu): `ADMIN-GUIDE-URDU.md`
- 📖 Deployment guide: `DEPLOY-README-URDU.md`
- 📖 CPI module guide: `CPI-SETUP-URDU.md`
- 📖 Performance tuning: `PERFORMANCE-PROFILES.md`
- 🐛 Issues: https://github.com/ronaldsexedwards40-glitch/dynabook/issues

---

**Made with ❤️ — Production-ready since May 2026**
