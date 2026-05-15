# Krexion — GitHub-Attached Permanent URL Setup

## 🎯 Problem aap solve karna chahte ho

> "Emergent preview URL sleep ho jata hai → admin panel band ho jata hai. Mujhe ek aisa URL chahiye jo **directly GitHub se chale**, Emergent ki kabhi zarurat na pade."

**Solution**: Krexion ko **cloud pe host karo, GitHub se auto-deploy hone do**. Aapke repo ka `main` branch update ho → URL pe app auto-update ho jaye.

---

## 🏆 RECOMMENDED: Render.com (Free + Paid options)

### Why Render?
- ✅ **GitHub se directly connected** — push karo → 5 min mein deploy
- ✅ **Permanent URL** — `https://krexion-XXXX.onrender.com` jo kabhi change nahi hoga
- ✅ **HTTPS free** — auto SSL certificate
- ✅ **24/7 uptime** (paid plan pe), free plan pe ~15 min idle ke baad sleep
- ✅ **No Emergent dependency**
- ✅ **No customer PC dependency** — cloud pe chalta hai
- ✅ **render.yaml file aapke repo mein add kar di hai** — bas blueprint deploy karo

### Pricing
| Component | Free Tier | Paid Tier |
|-----------|-----------|-----------|
| Backend (FastAPI) | $0 — sleeps after 15 min idle | $7/mo — always on |
| Frontend (React) | $0 — always free (static) | $0 — always free |
| MongoDB | $0 (use MongoDB Atlas) | $7/mo (Render managed) |
| **Total** | **$0/mo** (with cold starts) | **$14/mo** (production-grade) |

**Recommended**: Start with **free**, upgrade backend to paid ($7/mo) when you have paying customers.

---

## 📋 Setup Steps (Pehli baar — 20 min)

### Step 1: GitHub repo public/connected
✅ Already done — your repo `ronaldsexedwards40-glitch/dynabook` is public.

### Step 2: MongoDB Atlas (free 512 MB cluster)
1. Go to: https://mongodb.com/atlas/register
2. Sign up with Google (fastest)
3. Create FREE cluster:
   - Provider: AWS
   - Region: **Mumbai or Singapore** (closest to Pakistan/India)
   - Tier: **M0 Free**
4. **Database Access** → Add database user:
   - Username: `krexion`
   - Password: (generate strong, save it)
5. **Network Access** → Add IP Address → **"Allow Access From Anywhere"** (`0.0.0.0/0`)
6. **Connect** → Drivers → copy connection string. Looks like:
   ```
   mongodb+srv://krexion:<password>@cluster0.xxxxx.mongodb.net/krexion
   ```
   Replace `<password>` with the password you saved.

### Step 3: Sign up on Render.com
1. Go to: https://dashboard.render.com/register
2. Sign up with **GitHub** (one-click)
3. Authorize Render to access your `dynabook` repo

### Step 4: One-click deploy via Blueprint
1. Go to: https://dashboard.render.com/blueprints
2. Click **"New Blueprint Instance"**
3. Select repo: **`ronaldsexedwards40-glitch/dynabook`**
4. Render auto-detects `render.yaml` → shows preview of what will deploy
5. **Important**: Before clicking "Apply":
   - Find the `MONGO_URL` env var → click "Edit"
   - Paste your **MongoDB Atlas connection string** (from Step 2)
   - Save
6. Click **"Apply"**
7. Wait 10-15 min — Render builds + deploys everything

### Step 5: Get your URLs + admin password
After deploy completes:
1. Go to: https://dashboard.render.com → click `krexion-frontend`
2. Top of page shows: `https://krexion-frontend-XXXX.onrender.com` — **THIS IS YOUR PUBLIC URL**
3. Click `krexion-backend` → **Environment** tab → find `ADMIN_PASSWORD` → copy
4. Open frontend URL → login → admin@krexion.local / (the password you copied)

### Step 6: Bookmark + share
- Save `https://krexion-frontend-XXXX.onrender.com` in your phone bookmarks
- Share with team / customers
- Works on mobile, laptop, tablet — anywhere

---

## 🔄 How Auto-Deploy Works

```
You push code to GitHub main branch
         │
         ▼
Render gets webhook notification
         │
         ▼
Render runs docker build (backend)
Render runs yarn build (frontend)
         │
         ▼
New version deployed (5-10 min)
         │
         ▼
Your URL is now updated
```

**Every git push = automatic update**. You don't manually deploy ever again.

---

## 🆓 Want 100% Free? Use Vercel + Render Free + Atlas Free

If you don't want to pay anything:

### Frontend → Vercel (instead of Render free)
- Frontend deployments are faster on Vercel (no cold start)
- Free unlimited bandwidth

Steps:
1. https://vercel.com → sign up with GitHub
2. Import `ronaldsexedwards40-glitch/dynabook`
3. **Root Directory**: `frontend`
4. **Build Command**: `yarn build`
5. **Output Directory**: `build`
6. Env var: `REACT_APP_BACKEND_URL=https://krexion-backend-XXXX.onrender.com`
7. Deploy
8. You get URL like `https://dynabook.vercel.app` (custom name available)

### Backend → Render Free
- Use `plan: free` in render.yaml (change from `starter`)
- Will sleep after 15 min idle
- First request after sleep takes ~30 sec to wake up
- 750 hours/month free (enough for 1 service)

### Database → MongoDB Atlas Free
- Already covered in Step 2 above (M0 Free tier, 512 MB)

**Total cost: $0/month** with the trade-off that backend sleeps when idle.

---

## 🚀 Want Always-On for $5/month? Use DigitalOcean

If Render's $7/mo backend feels expensive:

### DigitalOcean App Platform
1. Sign up: https://digitalocean.com (use Pakistan-supported card or Payoneer)
2. Apps → Create App → Connect GitHub → Select dynabook
3. Auto-detects → click "Resources" → set:
   - Backend: $5/mo Basic plan (512 MB) — for LOW tier
   - Frontend: free static site
   - Database: $7/mo managed Mongo (or use free Atlas)
4. Deploy

**Total**: $5/mo (with Atlas free Mongo) or $12/mo (with DO Mongo)

---

## 🏠 Want Your OWN Domain (e.g. krexion.com)?

After cloud deployment is live:

1. **Buy domain** from Namecheap ($10/year) or Cloudflare Registrar
2. In Cloudflare DNS:
   - Add CNAME: `app.krexion.com` → `krexion-frontend-XXXX.onrender.com`
   - Add CNAME: `api.krexion.com` → `krexion-backend-XXXX.onrender.com`
3. In Render dashboard → Settings → Custom Domain:
   - Frontend: add `app.krexion.com`
   - Backend: add `api.krexion.com`
4. Render auto-issues SSL certificate (~5 min)
5. Update frontend env var `REACT_APP_BACKEND_URL=https://api.krexion.com`
6. Done — professional URL working

---

## 📊 Comparison: Customer PC vs Cloud

| Aspect | Customer's PC (current) | Cloud (Render) |
|--------|------------------------|----------------|
| Setup time | 15-30 min per customer | 20 min ONCE for you |
| URL | `http://localhost:3000` (their PC only) | Public worldwide URL |
| Mobile access | ❌ Only if Cloudflare Tunnel | ✅ Always |
| Uptime | When their PC is on | 24/7 always |
| Updates | Each customer must update | Auto-deploy from GitHub |
| Cost | Customer's electricity | $0-$14/mo for you |
| CPI Worker | ✅ Works (USB to phones) | ❌ Can't connect USB |

**Best hybrid model**:
- **Admin Panel + Web App** → Cloud (always-on URL for you/customers)
- **CPI Worker** → Customer's PC (needs USB for phones)
- Connect them via API (worker polls cloud backend)

---

## 🎯 What I Recommend (Practical Path)

### Phase 1 (This week — Free):
1. Sign up Render + Atlas (15 min)
2. Deploy via blueprint (`render.yaml` is in your repo)
3. Test the cloud URL — works from mobile
4. Use it as **your admin URL** (replaces Emergent preview)

### Phase 2 (When you have 5+ customers):
1. Upgrade Render backend to $7/mo (always-on, no sleep)
2. Buy `krexion.com` domain ($10/year)
3. Set up custom subdomain

### Phase 3 (When revenue justifies):
1. Move to DigitalOcean droplet ($25/mo) for full control
2. Add CDN (Cloudflare free)
3. Add multi-region for global users

---

## ❓ FAQ

**Q: Will Render free tier work for real customers?**
A: For testing/demo yes. For paid customers, the 30-sec cold start is unprofessional. Pay $7/mo for the backend.

**Q: Can I run Emergent preview AND Render at the same time?**
A: Yes! Emergent for active development, Render for production. Same GitHub repo feeds both.

**Q: What if I update code? Customers need to re-install?**
A: No! That's the magic of cloud deployment. You push to GitHub → Render auto-deploys → customers see update on next page refresh.

**Q: Krexion has Playwright (300 MB chromium). Will it fit in Render free?**
A: Free tier has 512 MB RAM and limited disk. **MIGHT** work for MICRO tier (1 RUT worker). For 2+ workers, you'll need paid plans.

**Q: What about CPI worker?**
A: CPI worker needs USB access to phones → can only run on a physical PC. Keep that on customer's PC. The cloud backend just receives data.

**Q: Render free has 750 hr/month, and 1 month = 720 hours. Will it fit?**
A: Yes — they're generous. If your service runs 24/7, that's 720 hr, under the 750 limit.

---

## 🔗 Quick Links

- Render dashboard: https://dashboard.render.com
- MongoDB Atlas: https://cloud.mongodb.com
- Vercel: https://vercel.com
- DigitalOcean: https://digitalocean.com
- Namecheap: https://namecheap.com
- Cloudflare: https://dash.cloudflare.com

---

## 🆘 Stuck? Common Issues

### "Build failed" on Render
- Check Render dashboard → backend service → Logs tab
- Most common: missing Python package in `backend/requirements.txt`
- Fix: add it, commit, push → auto-redeploy

### "Backend can't connect to MongoDB"
- Atlas Network Access → make sure `0.0.0.0/0` is whitelisted
- Connection string includes correct password (replace `<password>` placeholder)

### "Frontend shows blank page"
- Open browser DevTools (F12) → Console tab → look for CORS errors
- Backend env var `CORS_ORIGINS` must include the frontend URL
- Or set to `*` for testing

### "Login fails on cloud URL but works on Emergent"
- The cloud backend has its OWN admin password (auto-generated)
- Get it from Render dashboard → backend → Environment → `ADMIN_PASSWORD`
- Different from Emergent's `admin123`
