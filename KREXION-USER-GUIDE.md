# 📘 Krexion — Complete User Guide

**Version**: 1.0 (May 2026)
**Repo**: https://github.com/lenovogen03/lenovo-krexion
**Production**: https://krexion.com
**Backend**: https://api.krexion.com

> Yeh ek **complete book-style guide** hai. Kisi bhi heading pe click karen → seedha us section pe jump kar jayenge.

---

## 📑 Table of Contents (Click any item to jump)

### 🏁 Getting Started
1. [Krexion kya hai?](#1-krexion-kya-hai)
2. [System Requirements](#2-system-requirements)
3. [First-time Setup (One-time)](#3-first-time-setup-one-time)
4. [Daily Update / Resync](#4-daily-update--resync)
5. [Stop / Start / Restart Commands](#5-stop--start--restart-commands)

### 🔑 Login & Access
6. [User Login](#6-user-login)
7. [Admin Login](#7-admin-login)
8. [Forgot Password](#8-forgot-password)
9. [Sub-User Login](#9-sub-user-login)

### ⚙️ Admin Panel — One-Time Setup
10. [Admin Panel Tour](#10-admin-panel-tour)
11. [User Management](#11-user-management)
12. [Approve / Activate / Block Users](#12-approve--activate--block-users)
13. [Email Settings (Gmail / Resend)](#13-email-settings-gmail--resend)
14. [API Settings (Universal AI Vision Key)](#14-api-settings-universal-ai-vision-key)
15. [Branding (Logo, Colors, App Name)](#15-branding-logo-colors-app-name)
16. [System Check](#16-system-check)

### 📤 Uploaded Things (Data Sources)
17. [Uploaded Things Overview](#17-uploaded-things-overview)
18. [User Agents Upload](#18-user-agents-upload)
19. [Proxies Upload](#19-proxies-upload)
20. [Data Files Upload (Leads)](#20-data-files-upload-leads)
21. [Google Sheets Live Integration ⭐](#21-google-sheets-live-integration-)
22. [Smart Multi-Tab Picker](#22-smart-multi-tab-picker)
23. [Service Account JSON Setup (one-time)](#23-service-account-json-setup-one-time)

### 🔗 Links & Tracking
24. [Create a Tracked Link](#24-create-a-tracked-link)
25. [Click Stats & Analytics](#25-click-stats--analytics)
26. [Conversions & Postbacks](#26-conversions--postbacks)
27. [Postback URL Setup](#27-postback-url-setup)

### 🤖 Automation Engines
28. [Real User Traffic (RUT) — Survey Bot](#28-real-user-traffic-rut--survey-bot)
29. [Form Filler Engine](#29-form-filler-engine)
30. [CPI Worker (Android Phones)](#30-cpi-worker-android-phones)
31. [AI Vision Fallback (Gemini / OpenAI)](#31-ai-vision-fallback-gemini--openai)

### 🔔 Notifications & Alerts
32. [User Notifications Settings](#32-user-notifications-settings)
33. [Low-Stock Email Alert (Auto)](#33-low-stock-email-alert-auto)
34. [Custom Notification Email](#34-custom-notification-email)

### 🎨 Personalization
35. [Custom Theme Picker](#35-custom-theme-picker)
36. [Theme — Stat & Chart Box Colors](#36-theme--stat--chart-box-colors)

### 👥 Sub-Users (Multi-Account)
37. [Create Sub-Users](#37-create-sub-users)
38. [Sub-User Permissions](#38-sub-user-permissions)
39. [Track Sub-User Performance](#39-track-sub-user-performance)

### 🛠️ Maintenance & Troubleshooting
40. [Backup MongoDB Data](#40-backup-mongodb-data)
41. [Restore from Backup](#41-restore-from-backup)
42. [Logs — kahan check karen](#42-logs--kahan-check-karen)
43. [Common Errors & Fixes](#43-common-errors--fixes)
44. [Cloudflare Tunnel Issues](#44-cloudflare-tunnel-issues)
45. [Backend Not Starting](#45-backend-not-starting)
46. [Frontend Not Loading](#46-frontend-not-loading)

### 🔄 Updates & Deployment
47. [How to Update Code (KREXION-FORCE-SYNC)](#47-how-to-update-code-krexion-force-sync)
48. [Deploy Frontend to Vercel](#48-deploy-frontend-to-vercel)
49. [Backup Before Update](#49-backup-before-update)

### 📋 Reference
50. [File & Folder Structure](#50-file--folder-structure)
51. [All `.bat` Scripts Explained](#51-all-bat-scripts-explained)
52. [Default Credentials](#52-default-credentials)
53. [Emergency Recovery](#53-emergency-recovery)
54. [Glossary](#54-glossary)

---

# 🏁 Getting Started

## 1. Krexion kya hai?

Krexion ek **multi-feature traffic & lead automation platform** hai jo 4 main kaam karta hai:

| Module | Kya karta hai |
|---|---|
| **CPI Worker** | Android phones pe automatically apps install karke conversions generate karta hai |
| **Real User Traffic (RUT)** | Real browser sessions chala kar surveys/forms automatically fill karta hai (FlashRewards / RetailProductsUSA flow) |
| **Form Filler** | Custom form filling engine — koi bhi form, real user behavior simulation |
| **Link Tracking** | Branded short links, click analytics, conversion postbacks |

**Tech Stack**:
- 🐍 Backend: FastAPI + Python + Playwright + MongoDB
- ⚛️ Frontend: React + Tailwind (Vercel pe deploy)
- 🐳 Deploy: Docker Compose (Windows PC pe owner ka apna)
- ☁️ Public access: Cloudflare Tunnel

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 2. System Requirements

### Owner ki Windows PC (production server):
- Windows 10/11 (64-bit)
- 8 GB RAM minimum (16 GB recommended)
- 50 GB free disk space
- **Docker Desktop** installed → https://www.docker.com/products/docker-desktop/
- **Git for Windows** installed → https://git-scm.com/download/win
- Stable internet (for Cloudflare Tunnel)
- Cloudflare account (free) for tunnel setup

### CPI Worker (Android phones):
- USB-debugging enabled phones
- USB hub (recommended for multiple phones)
- ADB drivers installed

### End-users ka kuch nahi chahiye:
- Bas browser (Chrome / Firefox / Edge)
- App URL: https://krexion.com ya aapka custom domain

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 3. First-time Setup (One-time)

### **Step-by-step (~30 min):**

1. **Repo clone karen**:
   ```powershell
   cd F:\online
   git clone https://github.com/lenovogen03/lenovo-krexion.git
   cd lenovo-krexion
   ```

2. **`.env` file banayen** `backend/` folder mein:
   ```env
   JWT_SECRET_KEY=your-very-long-random-secret-min-32-chars
   ADMIN_EMAIL=admin@krexion.local
   ADMIN_PASSWORD=YourStrongAdminPassword123
   POSTBACK_TOKEN=any-secret-token-for-postback-auth
   APP_URL=https://krexion.com
   PUBLIC_BASE_URL=https://api.krexion.com
   TUNNEL_TOKEN=your-cloudflare-tunnel-token
   ```

3. **Cloudflare Tunnel setup karen**:
   - https://one.dash.cloudflare.com/ → Networks → Tunnels → Create
   - Naam: `krexion-tunnel`
   - Token copy karen → `.env` ke `TUNNEL_TOKEN` mein paste
   - Domain configure karen: `api.krexion.com → http://backend:8001`

4. **Service Account JSON download karen** (Google Sheets ke liye — optional but recommended):
   - https://console.cloud.google.com → New Project → "Krexion Sheets"
   - Sheets API enable karen
   - Service Account banayen → JSON key download
   - File rename karen: `gsheets-sa.json`
   - Path pe rakhen: `backend\secrets\gsheets-sa.json`
   - Detail steps: [Section 23](#23-service-account-json-setup-one-time)

5. **Docker Desktop chalu karen**

6. **`FRESH-DEPLOY.bat` ya `KREXION-FORCE-SYNC.bat` chalayen** (project folder mein double-click)

7. **Health check**: Browser mein khol ke verify karen:
   - `https://api.krexion.com/health` → `mongo_connected: true` aana chahiye

8. **Admin login** karen:
   - URL: https://krexion.com/admin
   - Email + Password jo `.env` mein set kiya
   - Detail: [Section 7](#7-admin-login)

9. **Email settings configure karen**: Admin Panel → Email tab → [Section 13](#13-email-settings-gmail--resend)

10. **First user banayen** ya register flow test karen

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 4. Daily Update / Resync

Jab bhi mein (agent) ya aap GitHub pe naye commits push karen, production wapas sync karne ke liye:

1. Project folder mein jayen:
   ```powershell
   cd F:\online\lenovo-krexion
   ```

2. **`KREXION-FORCE-SYNC.bat`** chalayen (double-click ya CMD se):
   ```cmd
   KREXION-FORCE-SYNC.bat
   ```

3. Yeh khud kar lega:
   - `git fetch + reset --hard origin/main`
   - Docker `--no-cache` rebuild
   - Container restart

**Time**: 3-5 min

⚠️ **Backup pehle lena chahiye** — [Section 49](#49-backup-before-update)

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 5. Stop / Start / Restart Commands

| Action | Script | Command (manual) |
|---|---|---|
| **Stop all** | `KREXION-STOP.bat` | `docker compose down` |
| **Start all** | `KREXION-AUTO.bat` | `docker compose up -d` |
| **Restart backend only** | — | `docker compose restart backend` |
| **Rebuild backend** | `KREXION-UPDATE.bat` | `docker compose up -d --build backend` |
| **Force fresh** | `KREXION-FORCE-SYNC.bat` | (See script) |
| **View logs** | `KREXION-LOGS.bat` | `docker compose logs -f backend` |
| **Diagnose** | `DIAGNOSE.bat` | (Container/network check) |

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 🔑 Login & Access

## 6. User Login

**URL**: https://krexion.com/login

1. Email + password daalen
2. **Login** click karen
3. Sidebar pe jo features admin ne enable kiye hain woh dikhenge:
   - Dashboard
   - Links
   - Clicks
   - Conversions
   - Real User Traffic
   - Form Filler
   - Import Traffic
   - Uploaded Things
   - Settings
   - (Sub-Users / CPI / Branding — agar enable hain)

**First-time register**: https://krexion.com/register
- Naam, email, password daal ke register karen
- Status `pending` rahegi
- Admin approve karega phir login karke features mil jayenge

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 7. Admin Login

**URL**: https://krexion.com/admin

1. Email: `admin@krexion.local` (ya jo `ADMIN_EMAIL` `.env` mein set hai)
2. Password: jo `ADMIN_PASSWORD` `.env` mein set hai
3. **Sign In as Admin** click karen
4. Redirect → Admin Dashboard (`/admin/dashboard`)

⚠️ Admin password change karna ho toh `.env` edit karen aur backend restart:
```cmd
docker compose restart backend
```

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 8. Forgot Password

User ke liye:
1. Login page → **"Forgot Password?"** click karen
2. Email daalen → "Send Reset Link"
3. Email check karen — Krexion se 1-hour-valid reset link aayega
4. Link click karen → naya password set karen → done

⚠️ **Email feature kaam karega tab hi** jab admin ne **Email Settings** configure ki ho — [Section 13](#13-email-settings-gmail--resend)

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 9. Sub-User Login

Sub-users primary user ke "junior accounts" hote hain:
1. **URL**: https://krexion.com/login (same login page)
2. Sub-user ka email + password (jo primary user ne set kiya hota hai)
3. Login karte hi limited features dikhenge (jo primary user ne unko diye hain)

Detail: [Section 37-39](#37-create-sub-users)

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# ⚙️ Admin Panel — One-Time Setup

## 10. Admin Panel Tour

Admin login ke baad **`/admin/dashboard`** pe redirect hota hai. 6 tabs:

| Tab | Kya karta hai |
|---|---|
| **User Management** | Saare users list, approve/block, features assign |
| **Sub-Users** | Aggregate view of all sub-users across primary accounts |
| **Branding** | Logo, app name, colors set karna |
| **API Settings** | Universal AI Vision API key (server-wide) |
| **Email** ⭐ | Gmail/Resend setup (centralized for all users) |
| **System Check** | Health, DB, Mongo, Cloudflare status |

Top pe stats: Total Users, Sub-Users, Total Links, Total Clicks, Total Conversions

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 11. User Management

### **Users list dekhne ke liye**:
Admin Dashboard → User Management tab

### **Filters**:
- All / Active / Pending / Blocked
- Search by email/name

### **Per user actions** (right side dropdown):
- ✏️ Edit (status, features, password)
- ✅ Activate (pending → active)
- 🚫 Block / Unblock
- 🗑️ Delete (irreversible — careful!)

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 12. Approve / Activate / Block Users

### **Naya user register hua hai (status: pending)**:
1. Admin Panel → User Management
2. Filter: **"Pending"** select karen
3. Us user ke samne **"Edit"** click karen (pencil icon)
4. **Status** dropdown: `pending` → `active`
5. **Features** section mein checkboxes:
   - ✅ Real User Traffic
   - ✅ Form Filler
   - ✅ Import Data
   - ✅ Links / Clicks / Conversions
   - ✅ CPI (agar permission deni)
   - ✅ Sub-Users (agar sub-user banane ki permission deni)
6. **"Save changes"** click karen
7. User ko email aayegi (agar email config ho) ya manually batayen

### **User block karna**:
- Edit → Status: `blocked` → Save
- User login nahi kar payega
- Sub-users bhi block ho jayenge

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 13. Email Settings (Gmail / Resend)

⭐ **Yeh ek-baar setup karne ki cheez hai** taake low-stock alerts, password resets, notifications sab kaam karen.

### **Option A — Gmail (free, 5 min)** — RECOMMENDED for &lt;500 emails/day

**Step 1: Gmail account ki 2-Step Verification ON karen**
1. https://myaccount.google.com/security
2. "2-Step Verification" → On karen
3. Phone number verify karen

**Step 2: App Password generate karen**
1. https://myaccount.google.com/apppasswords
2. App name: `Krexion`
3. **Create** click karen
4. **16-character password copy karen** (jaise `abcd efgh ijkl mnop`)
5. ⚠️ Sirf ek baar dikhega — turant copy karen

**Step 3: Krexion Admin Panel mein paste karen**
1. Admin Login → `/admin/dashboard`
2. **Email** tab click karen
3. **Email Provider** dropdown: **Gmail SMTP (recommended)**
4. **Gmail address**: `aapka@gmail.com`
5. **Gmail App Password**: 16-char password paste (spaces ke saath ya bina, dono chalte hain)
6. **Sender name**: `Krexion Alerts` (ya jo dikhana ho inbox mein "From" pe)
7. **"Save email settings"** click karen → toast "✅ Email settings saved"

**Step 4: Test karen**
1. **"test@youremail.com"** input mein apni email daalen (ya blank — admin email pe jayegi)
2. **"Send test email"** click karen
3. Toast aana chahiye: "✅ Test email sent via smtp to ..."
4. Inbox check karen — `Krexion Alerts` se email aayegi

### **Option B — Resend (free 3,000/month, custom domains)**

1. https://resend.com/signup → account banayen
2. https://resend.com/api-keys → "Create API Key" → naam `Krexion`, permission `Sending access`
3. Copy karen `re_xxxxxxxx...`
4. (Optional) https://resend.com/domains → apna domain verify karen
5. Admin Panel → Email tab:
   - Provider: **Resend**
   - API Key: paste
   - From: `alerts@yourdomain.com` ya testing ke liye `onboarding@resend.dev`
   - Save → Test

### **Option C — Custom SMTP** (SendGrid / Mailgun / AWS SES / etc.)
- Provider: **Custom SMTP**
- Host, Port, User, Password fill karen
- Save → Test

### **Option D — Disabled**
- Sirf logs mein dikhega, koi email nahi jayegi
- Testing ke liye useful

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 14. API Settings (Universal AI Vision Key)

AI Vision Fallback ke liye Gemini ya OpenAI key. Agar admin yahan key add kare toh saare users use kar sakenge bina apni-apni keys ke. Per-user override bhi ho sakta hai (Settings → AI Vision Fallback).

### **Gemini key (free)**:
1. https://aistudio.google.com/app/apikey
2. "Create API Key" → copy karen
3. Admin Panel → API Settings → Provider: Gemini → Key: paste → Save

### **OpenAI key (paid)**:
1. https://platform.openai.com/api-keys → "Create new secret key"
2. Copy `sk-...`
3. Admin Panel → API Settings → Provider: OpenAI → Key: paste → Save

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 15. Branding (Logo, Colors, App Name)

Admin Panel → Branding tab:

| Field | Description |
|---|---|
| **App Name** | "Krexion" → kuch aur set kar sakte hain |
| **Logo URL** | Image URL (host on imgur/cloudinary) ya base64 |
| **Primary Color** | Buttons, accents |
| **Background Color** | Page bg |
| **Card Color** | Stat boxes, charts |
| **Border Color** | Lines |

⚠️ Aapki branding settings kaam karenge tab tak jab user ne "Custom" theme select nahi kiya ho. Custom theme priority leta hai. ([Section 35](#35-custom-theme-picker))

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 16. System Check

Admin Panel → System Check tab:

Ek "diagnostic page" jo dikhata hai:
- ✅ Backend health
- ✅ MongoDB connection
- ✅ AI Vision key configured
- ✅ Email config status
- ✅ Cloudflare tunnel status
- ✅ Disk space
- ✅ Active jobs running

Agar koi cheez red ho toh wahin se troubleshoot karen.

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 📤 Uploaded Things (Data Sources)

## 17. Uploaded Things Overview

User Side → **Uploaded Things** page

3 types of uploads:

| Type | Kya hota hai |
|---|---|
| **User Agents (UAs)** | Browser fingerprint strings, RUT mein har visit pe rotate hoti hain |
| **Proxies** | IP addresses for rotation, mostly residential proxies |
| **Data Files (Leads)** | first/last/email/state/zip etc. ke records — surveys mein use hote hain |

Har type 2 mode mein add ho sakta hai:
- 📁 **File / Text Upload** (xlsx / one-per-line text)
- 🌐 **Google Sheet URL (live)** ⭐ — recommended for production

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 18. User Agents Upload

1. Uploaded Things → **User Agents / Networks** tab
2. **"+ Add UAs"** button
3. **Mode**:
   - **Text/File**: Paste UAs (one per line) ya XLSX upload
   - **Google Sheet URL (live)**: paste sheet URL → Smart Picker se tab choose
4. Ek descriptive name den: `iPhone-iOS17-UAs`
5. **Upload** click karen

**Live mode** mein har RUT job sheet se fresh UA pull karega aur consumed UAs auto-skip honge.

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 19. Proxies Upload

Same flow as UAs:
1. Uploaded Things → **Proxies** tab
2. **"+ Add Proxies"**
3. Format: `user:pass@host:port` per row
4. Mode: Text / File / Google Sheet
5. Name: `Residential-USA-Pool`
6. Upload

⚠️ **Live mode + auto-skip-after-use** ensures same IP duplicate jobs mein nahi pickta.

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 20. Data Files Upload (Leads)

1. Uploaded Things → **Data Files** tab
2. **"+ Add Data File"**
3. Mode: XLSX upload ya Google Sheet URL
4. Required columns (first row = header):
   - `first` (first name)
   - `last` (last name)
   - `email` ⭐ (zaruri — auto-skip & alert tracking ke liye)
   - `state`, `zip`, `address`, `phone` etc. (job-specific)
5. Name: `Leads-CA-Survey-Q2`
6. Upload

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 21. Google Sheets Live Integration ⭐

**Best feature** — sheet hi single source of truth ban jaata hai:

### **Faiday**:
- Sheet kabhi bhi edit karen — Krexion auto-pickup karega next job pe
- MongoDB pe load nahi padta
- **Live row deletion**: jaise jaise rows use hote hain, sheet se physically delete hote jate hain

### **Setup (one-time, ~2 min)**:

1. **Service Account JSON** chahiye → [Section 23](#23-service-account-json-setup-one-time)

2. **Sheet share karen**:
   - Google Sheet kholen → top right "Share" button
   - Option 1: **"Anyone with the link → Editor"** (easiest)
   - Option 2: Service Account email ko **Editor** banake share (private sheets)

3. **URL copy karen**:
   - Sheet ke andar **specific tab** pe click karen jo aap upload mein attach karna chahte hain
   - Browser address bar se pura URL copy karen (us mein `#gid=...` hoga)

4. **Krexion mein paste karen**:
   - Uploaded Things → koi bhi tab → "Google Sheet URL (live)" mode select karen
   - URL paste karen → 600ms wait
   - **Smart Tab Picker** dropdown khulega: saare tabs with row counts
   - Apni tab select karen → "Link Google Sheet" click

5. **Verify**:
   - Upload card pe **green "LIVE EDIT" badge** dikhna chahiye
   - "↗ Open sheet" + tab label + "X rows left" status visible

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 22. Smart Multi-Tab Picker

Ek master spreadsheet, multiple tabs (e.g. `Proxies`, `UAs`, `Leads-CA`, `Leads-TX`) — each tab attach to different upload type.

### **Workflow**:

1. Google Sheets mein **ek master spreadsheet** banayen: e.g. "Krexion Data Hub"
2. Andar tabs banayen: `Proxies`, `UAs`, `Leads-CA`
3. "Anyone with link → Editor" share karen
4. Krexion mein:
   - Proxies upload mein master sheet URL paste karen → dropdown se "Proxies" tab select
   - UAs upload mein same URL paste karen → dropdown se "UAs" tab select
   - Data Files upload mein same URL → "Leads-CA" tab select

**Result**: Ek hi spreadsheet mein sab manage, alag-alag uploads mein attach.

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 23. Service Account JSON Setup (one-time)

### **Step 1: Google Cloud Console**

1. https://console.cloud.google.com pe jayen
2. Top dropdown → **"New Project"**
3. Name: `krexion-sheets` → Create

### **Step 2: Sheets API enable**
1. Left menu → **APIs & Services** → **Library**
2. Search: "Google Sheets API"
3. Click → **"Enable"**

### **Step 3: Service Account banayen**
1. **APIs & Services** → **Credentials**
2. **+ Create Credentials** → **Service Account**
3. Name: `krexion-bot` → Create → Done

### **Step 4: JSON key download**
1. Service account list mein `krexion-bot@xxx.iam.gserviceaccount.com` pe click
2. **Keys** tab → **Add Key** → **Create new key** → **JSON** → Create
3. Ek `.json` file download ho jayegi

### **Step 5: File ko sahi jagah rakhen**
1. Apni Windows PC pe project folder kholen:
   ```
   C:\Krexion\backend\
   ```
2. **`secrets`** folder banayen (agar nahi hai)
3. Downloaded JSON file ko rename karen: **`gsheets-sa.json`**
4. Us folder mein paste karen:
   ```
   backend\secrets\gsheets-sa.json
   ```

### **Step 6: Restart**
- `KREXION-FORCE-SYNC.bat` chalayen ya `docker compose restart backend`

### **Verify**:
- Uploaded Things mein gsheet upload karen → green "LIVE EDIT" badge dikhna chahiye

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 🔗 Links & Tracking

## 24. Create a Tracked Link

1. User side → **Links** page
2. **"+ Create Link"** button
3. **Destination URL**: e.g. `https://offer.com/landing-page`
4. **Branded short** (optional): `summer-deal`
5. **Network**: dropdown se network select (AppsFlyer / Adjust / Branch / generic)
6. **Macro params**: `{click_id}`, `{country}` etc. supported hain
7. **Create**

### Generated short link milega: `https://krexion.com/r/abc123`

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 25. Click Stats & Analytics

User side → **Clicks** page

Real-time stats:
- Total clicks per link
- Unique clicks (by IP+UA hash)
- Country breakdown
- Device breakdown (mobile / desktop / tablet)
- Browser breakdown
- Time-series chart (clicks per hour/day)

Filters: date range, link, country, device

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 26. Conversions & Postbacks

User side → **Conversions** page

Conversions tab pe:
- Total conversions
- Revenue / payouts
- Per-link conversion rate
- Top performing links

Postback flow:
1. Network conversion fire karta hai → Krexion ka postback URL hit karta hai
2. Krexion conversion record karta hai
3. Dashboard pe real-time update

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 27. Postback URL Setup

### **Aapka unique postback URL**:
```
https://api.krexion.com/api/postback/{your-postback-token}?click_id={click_id}&payout={payout}&status=approved
```

### **Network mein register karen**:

#### AppsFlyer:
1. AppsFlyer dashboard → Configuration → Integrated Partners → search "Custom"
2. Postback URL paste karen
3. Macros: `{click_id}` → AppsFlyer's `clickid`, `{payout}` → `revenue`

#### Adjust:
1. Adjust → Settings → Postbacks → Add
2. Same URL, AdjustIDs map karen

#### Branch:
1. Branch dashboard → Webhooks
2. Add custom webhook → URL paste

### **Test karen**:
```bash
curl "https://api.krexion.com/api/postback/your-token?click_id=test123&payout=2.50&status=approved"
```

Expected: `{"status":"ok"}`

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 🤖 Automation Engines

## 28. Real User Traffic (RUT) — Survey Bot

User side → **Real User Traffic** page

### **Job banane ka tarika**:

1. **"+ New RUT Job"** click karen
2. **Settings**:
   - **Target URL**: jis sheet pe redirect karna hai (offer landing page)
   - **Visits count**: 100 (start small)
   - **Concurrency**: 3 (parallel browsers)
   - **UAs source**: dropdown → koi gsheet/upload select
   - **Proxies source**: dropdown
   - **Data file** (optional): leads source for surveys
3. **Survey flow** (advanced):
   - **FlashRewards** preset
   - **RetailProductsUSA** preset
   - **Custom flow** (JSON automation)
4. **Schedule** (optional): "Run now" ya specific time
5. **Create Job**

### **Live Activity panel**:
- Har visit ka real-time status
- Screenshots after each step
- Success / failure breakdown
- Conversion postback fired count

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 29. Form Filler Engine

User side → **Form Filler** page

Custom form filling — RUT ka subset jo specifically forms ke liye optimized hai.

1. **+ New Form Filler Job**
2. **Target form URL**
3. **Field mapping**: detect button → confirm fields → map to data file columns
4. **Submit count**, concurrency, proxies, UAs
5. **Run**

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 30. CPI Worker (Android Phones)

⚠️ **Production-only feature** — physical phones chahiye

### **Setup**:
1. Phone USB-debugging enable karen (Developer options)
2. PC mein USB se connect karen
3. **`CPI-ONE-CLICK.bat`** chalayen
4. ADB se phone detect hote hi Krexion ko notify karega
5. Krexion → CPI page → connected devices list

### **Job ka flow**:
1. CPI page → **+ New CPI Campaign**
2. **App package name**: `com.example.app`
3. **Install source**: Play Store / direct APK URL
4. **Phones**: select connected phones
5. **Postback**: configure conversion postback
6. **Run**

CPI worker khud:
- App install karega
- 30 sec wait + open
- Conversion postback fire
- Uninstall (optional)
- Repeat per phone

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 31. AI Vision Fallback (Gemini / OpenAI)

Jab RUT ka rule-based selector fail ho jaye (page layout badal gaya), AI Vision screenshot le ke decide karta hai kahan click karna hai.

### **User-side setup** (per-user, override admin):
1. User Settings → **AI Vision Fallback** tab
2. **Provider**: Gemini ya OpenAI
3. **API Key**: paste
4. Save

### **Server-wide** (admin):
- Admin Panel → API Settings ([Section 14](#14-api-settings-universal-ai-vision-key))
- Saare users use karenge agar khud ki key nahi rakhi

### **Free Gemini key**:
- https://aistudio.google.com/app/apikey
- "Create API Key" — free tier 1,500 requests/day

### **Logs check**:
- Job run hote waqt "AI fallback fired" entries dikhenge
- Per-job decision JSON logged hota hai (Future feature: AI Decision Log viewer)

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 🔔 Notifications & Alerts

## 32. User Notifications Settings

User side → **Settings** page → **Notifications** tab

### **Configure**:
1. **Notification email**: blank chhoden (login email use hogi) ya alag email daalen (e.g. `ops@mycompany.com`)
2. **Enable low-stock alerts** toggle: ON
3. **Save notification settings**

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 33. Low-Stock Email Alert (Auto)

### **Kab fire hota hai**:
- Koi gsheet upload mein **≤ 10% rows** baaki rah jaayen
- Example: 1,000 rows mein se 100 ya kam bachen

### **Email content**:
- Subject: "⚠ Low-stock: <upload_name> (X of Y rows left)"
- Pretty HTML body with rows-remaining counter, "Open Sheet & Refill →" button
- Direct link to sheet

### **Idempotency**:
- Per depletion ek hi email — no spam
- Sheet refill karte hi flag clear ho jata hai → next depletion par dobara email

### **Pre-requisite**:
- Admin ne **Email Settings** configure ki ho ([Section 13](#13-email-settings-gmail--resend))

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 34. Custom Notification Email

Aap chahein ke alerts apke login email pe na aaen — kisi ops/team email pe jayen:

1. User Settings → Notifications tab
2. **Notification email** field mein alag email daalen (e.g. `team-alerts@company.com`)
3. Save

Phir saari notifications us email pe jayengi.

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 🎨 Personalization

## 35. Custom Theme Picker

Top-right corner mein **🎨 palette icon** click karen.

3 themes:
- ☀️ **Day** (light)
- 🌙 **Night** (dark, default)
- 🎨 **Custom** — apne colors choose karen

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 36. Theme — Stat & Chart Box Colors

**Custom theme** select karen → 7 swatches dikhenge:

| Swatch | Kya control karta hai |
|---|---|
| **Primary** | Main buttons, links, accent borders |
| **Accent** | Secondary highlights |
| **Background** | Page bg |
| **Card (stat & chart boxes)** ⭐ | Total Clicks, Conversions, charts ka bg |
| **Card Elevated (inputs)** ⭐ | Input fields, dropdowns, sub-cards ka bg |
| **Text** | Main text color |
| **Border** | All borders |

Color picker click karen → hex daalen ya color wheel use karen → instantly preview update hota hai.

⚠️ Aapka theme localStorage mein save hota hai — refresh karne pe bhi rahega.

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 👥 Sub-Users (Multi-Account)

## 37. Create Sub-Users

User Settings → **Sub-Users** tab (agar feature enabled hai)

1. **+ Create Sub-User** button
2. Naam, email, password set karen
3. **Permissions**: kuch features select karen jo sub-user ke paas honge
4. Create

Sub-user ko email ya manual basis pe credentials den.

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 38. Sub-User Permissions

| Permission | Description |
|---|---|
| Links | Apne tracked links bana sakta hai |
| Clicks | Click stats dekh sakta hai |
| Conversions | Conversion stats |
| RUT | Real User Traffic jobs |
| Form Filler | Form filler jobs |
| Uploaded Things | Apne uploads (separate from primary) |
| CPI | (rarely given to sub-users) |

Primary user kabhi bhi permissions edit kar sakta hai.

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 39. Track Sub-User Performance

User Settings → Sub-Users → har sub-user ke samne **"View Stats"**:
- Sub-user ka apne clicks/conversions
- Aggregate primary user ke under

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 🛠️ Maintenance & Troubleshooting

## 40. Backup MongoDB Data

⚠️ **Update / restart se pehle hamesha backup len**.

### **Manual backup**:
```cmd
docker exec krexion-mongo mongodump --out=/data/db/backup-2026-05-04
docker cp krexion-mongo:/data/db/backup-2026-05-04 F:\krexion-backups\
```

### **Automated** (recommended):
1. Task Scheduler kholen (Windows)
2. New task: daily 3 AM
3. Action: `docker exec krexion-mongo mongodump --out=/data/db/backup-%date%`

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 41. Restore from Backup

```cmd
docker cp F:\krexion-backups\backup-2026-05-04 krexion-mongo:/data/db/restore
docker exec krexion-mongo mongorestore --drop /data/db/restore
docker compose restart backend
```

⚠️ `--drop` flag se existing data delete ho jayega — careful!

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 42. Logs — kahan check karen

| Log | Command |
|---|---|
| **Backend** | `docker compose logs -f backend` |
| **MongoDB** | `docker compose logs -f mongo` |
| **Cloudflare Tunnel** | `docker compose logs -f cloudflared` |
| **All** | `docker compose logs -f` |

Easy way: `KREXION-LOGS.bat` double-click karen.

Filter karna ho:
```cmd
docker compose logs backend | findstr "ERROR"
```

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 43. Common Errors & Fixes

| Error | Reason | Fix |
|---|---|---|
| **Backend healthcheck fail** | Mongo not connected | `docker compose restart mongo backend` |
| **"Invalid credentials" admin login** | `.env` me password galat ya container restart nahi hua | `.env` check + `docker compose restart backend` |
| **CORS error in browser** | `CORS_ORIGINS` `.env` mein nahi set | `CORS_ORIGINS=*` set karen + restart |
| **Cloudflare 502** | Tunnel down ya backend down | `DIAGNOSE.bat` chalayen |
| **Email not sending** | Provider config galat ya 2-Step ON nahi | Admin Panel → Email → "Send test email" se check |
| **Gsheet "no LIVE EDIT badge"** | SA JSON missing ya path galat | `backend/secrets/gsheets-sa.json` verify karen + restart |
| **RUT job stuck** | Playwright browser crash | `docker compose logs backend` check + restart |
| **Frontend "Network Error"** | Backend URL galat | Vercel env: `REACT_APP_BACKEND_URL` verify |

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 44. Cloudflare Tunnel Issues

### **Tunnel down**:
1. https://one.dash.cloudflare.com/ → Tunnels
2. Status check — kya "Healthy" hai?
3. Agar "Inactive": `docker compose up -d cloudflared` (or `--profile tunnel`)
4. Token check: `.env` mein `TUNNEL_TOKEN` correct?
5. **`FIX-TUNNEL.bat`** chalayen — automated fix

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 45. Backend Not Starting

```cmd
docker compose logs backend | tail -50
```

Common issues:
- **Port 8001 already in use**: `netstat -ano | findstr :8001` → kill that PID
- **Mongo connection refused**: `docker compose logs mongo` check
- **Module not found**: `docker compose build --no-cache backend`
- **`.env` parsing error**: `.env` mein quotes / spaces check

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 46. Frontend Not Loading

Frontend Vercel pe deploy hota hai:
1. https://vercel.com/dashboard → apna project kholen
2. **Deployments** tab → latest deploy status
3. Agar fail: **Logs** check karen
4. **Settings** → **Environment Variables**: `REACT_APP_BACKEND_URL=https://api.krexion.com` set hai?
5. **Re-deploy**: Deployments → "..." → Redeploy

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 🔄 Updates & Deployment

## 47. How to Update Code (KREXION-FORCE-SYNC)

Already covered in [Section 4](#4-daily-update--resync). Quick recap:

1. Project folder mein **`KREXION-FORCE-SYNC.bat`** double-click
2. 3-5 min wait
3. Verify `https://api.krexion.com/health`

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 48. Deploy Frontend to Vercel

Frontend automatically deploy hota hai jab GitHub `main` branch update hoti hai (Vercel ki auto-deploy feature).

Manual trigger:
1. Vercel dashboard → project → **Deployments** → "..." → **Redeploy**

Naya domain add karna ho:
1. Vercel → project → **Settings** → **Domains** → "Add" → `app.yourdomain.com`
2. DNS records jo Vercel batayega woh apne domain provider pe set karen

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 49. Backup Before Update

⚠️ **Hamesha update se pehle backup len** — kabhi-kabhi migration scripts data structure change kar dete hain.

```cmd
docker exec krexion-mongo mongodump --out=/data/db/pre-update-backup
```

Phir `KREXION-FORCE-SYNC.bat` chalayen.

Agar update ke baad kuch tut jaye, [Section 41](#41-restore-from-backup) se restore karen.

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 📋 Reference

## 50. File & Folder Structure

```
lenovo-krexion/
├── backend/                      # FastAPI + Python backend
│   ├── server.py                 # Main app (~11.6k lines)
│   ├── notifications.py          # Email + low-stock alerts
│   ├── gsheet_writer.py          # Google Sheets API helpers
│   ├── form_filler.py            # Form filling engine
│   ├── real_user_traffic.py      # RUT survey bot engine
│   ├── ai_automation_generator.py # AI Vision fallback
│   ├── secrets/                  # Service Account JSONs (gitignored)
│   │   └── gsheets-sa.json       # ← yahan rakhna hai aapko
│   ├── uploaded_resources/       # User XLSX uploads (mounted volume)
│   ├── real_user_traffic_results/# Job results (mounted volume)
│   ├── requirements.txt
│   ├── .env                      # Production secrets (gitignored)
│   └── Dockerfile
├── frontend/                     # React app
│   ├── src/
│   │   ├── pages/                # Login, Dashboard, Admin, Settings, etc.
│   │   ├── components/           # Reusable UI components
│   │   ├── context/              # ThemeContext, BrandingContext
│   │   └── ...
│   └── package.json
├── krexion-cpi-worker/          # Native Python CPI worker (Windows)
├── deployment/                   # Cloudflare configs, deploy scripts
├── memory/                       # Documentation
├── tests/                        # Test scripts
├── docker-compose.yml            # Production stack
├── *.bat / *.ps1                 # Windows automation scripts
└── README.md
```

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 51. All `.bat` Scripts Explained

| Script | Use case |
|---|---|
| **KREXION-AUTO.bat** | First-time auto setup (full pipeline) |
| **KREXION-FORCE-SYNC.bat** ⭐ | Pull latest code + rebuild + restart (use after every update) |
| **KREXION-UPDATE.bat** | Light update (no `--no-cache` rebuild) |
| **KREXION-STOP.bat** | Stop all containers |
| **KREXION-LOGS.bat** | Tail backend logs in real-time |
| **KREXION-DOCTOR.bat** | Health diagnostics |
| **KREXION-LOGIN-FIX.bat** | Re-seed admin if login issues |
| **KREXION-DEPLOY.ps1** | PowerShell version of deploy (with more options) |
| **DIAGNOSE.bat** | Network + container diagnostics |
| **FIX-TUNNEL.bat** | Cloudflare tunnel automated fix |
| **FRESH-DEPLOY.bat** | Wipe + redeploy (DANGEROUS — backup first) |
| **CPI-ONE-CLICK.bat** | CPI worker auto-setup (USB ADB) |
| **CPI-PROXY-BRIDGE-TEST.bat** | Test phone-side proxy routing |
| **ADMIN-CREDENTIALS-MANAGER.bat** | Reset / rotate admin credentials |
| **ONE-CLICK-ADMIN-RESET.bat** | Quick admin password reset |
| **ONE-CLICK-UPGRADE.bat** | Major version upgrade |

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 52. Default Credentials

| Account | Default |
|---|---|
| **Admin email** | `admin@krexion.local` (in `.env` `ADMIN_EMAIL`) |
| **Admin password** | Set in `.env` `ADMIN_PASSWORD` |
| **MongoDB user** | None (no auth — internal Docker network only) |
| **Postback token** | Set in `.env` `POSTBACK_TOKEN` |

⚠️ Production mein ALL passwords change karen aur strong rakhen.

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 53. Emergency Recovery

### **Sab kuch broke ho gaya**:

1. **Stop**: `KREXION-STOP.bat`
2. **Backup MongoDB volume**:
   ```cmd
   docker run --rm -v krexion_mongo-data:/data -v F:\backups:/backup ubuntu tar czf /backup/mongo-emergency.tar.gz /data
   ```
3. **Fresh clone karen**:
   ```cmd
   cd F:\online
   git clone https://github.com/lenovogen03/lenovo-krexion.git krexion-fresh
   cd krexion-fresh
   ```
4. **Configure** `.env` + `backend/secrets/gsheets-sa.json`
5. **`FRESH-DEPLOY.bat`** chalayen
6. **Restore Mongo** (agar zarurat ho):
   ```cmd
   docker compose stop backend
   docker run --rm -v krexion-fresh_mongo-data:/data -v F:\backups:/backup ubuntu tar xzf /backup/mongo-emergency.tar.gz -C /
   docker compose start backend
   ```

### **Worst case**: Mujhe (agent) batayen, mein step-by-step recover kar dunga

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

## 54. Glossary

| Term | Meaning |
|---|---|
| **CPI** | Cost Per Install — Android app installation conversions |
| **RUT** | Real User Traffic — Real browser-based survey/form automation |
| **UA** | User Agent — Browser fingerprint string |
| **Proxy** | IP address used for routing requests (residential / datacenter) |
| **Postback** | Server-to-server conversion notification URL |
| **Cloudflare Tunnel** | Secure way to expose local Docker services to public internet |
| **Service Account** | Google Cloud "robot user" for automated API access |
| **gid** | Google Sheets tab/worksheet unique ID (in URL `#gid=N`) |
| **App Password** | Gmail's 16-char SMTP password for apps (not regular password) |
| **Sub-user** | Junior account under primary user with limited permissions |
| **Depletion** | Gsheet upload rows count dropping below 10% |

[⬆ Back to TOC](#-table-of-contents-click-any-item-to-jump)

---

# 🎯 Quick Reference Card (Print & Stick on Wall)

```
┌─────────────────────────────────────────────────────┐
│  Krexion Daily Operations                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Update code:    KREXION-FORCE-SYNC.bat            │
│  Stop server:    KREXION-STOP.bat                  │
│  Start server:   KREXION-AUTO.bat                  │
│  View logs:      KREXION-LOGS.bat                  │
│  Health check:   https://api.krexion.com/health │
│  Admin login:    https://krexion.com/admin       │
│  User login:     https://krexion.com/login       │
│  Repo:           github.com/lenovogen03/lenovo-krexion │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

# 📞 Support

- **GitHub Issues**: https://github.com/lenovogen03/lenovo-krexion/issues
- **Docs**: This file (`KREXION-USER-GUIDE.md`)
- **Owner**: lenovogen03

---

**End of Guide** · Last updated: May 2026
