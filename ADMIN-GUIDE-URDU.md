# 🛠️ Krexion Admin — Self-Manage Guide

Aap kahin se bhi, kisi bhi computer/mobile pe, GitHub web UI se 3 cheezein khud manage kar sakte ho:
1. 🔴 Kill-switch (REVOKE / ACTIVATE)
2. ⏰ Expiry date extend / change
3. 🔑 Activation key change

**Pehli baat**: GitHub pe login zaroori hai (`ronaldsexedwards40-glitch` account).

---

## 🛠️ ADMIN TOOLKIT (yeh aap ka best friend hai)

Maine ek HTML page banaya hai jo aap ke browser mein khud key hash + expiry date calculate karta hai.

### Khol kaise karein?

**Option 1 — GitHub se direct (mobile/laptop kahin bhi)**
1. Yeh link kholein: https://github.com/ronaldsexedwards40-glitch/dynabook/blob/main/ADMIN-TOOLKIT.html
2. Top-right pe **"Raw"** button click karein
3. URL ko **`raw.githubusercontent.com`** se replace karke kholein, ya...
4. Better: yeh shortcut link bookmark kar lein:
   ```
   https://htmlpreview.github.io/?https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main/ADMIN-TOOLKIT.html
   ```
   (HTML preview service — page open ho jaye gi)

**Option 2 — Local pe**
- `C:\krexion\ADMIN-TOOLKIT.html` file ko double-click karein → default browser mein khul jaye gi

**Option 3 — GitHub Pages (cleanest)** *(advanced - chahien toh setup karein)*
- Repo Settings → Pages → Source: `main` branch root → save
- 1 min baad: `https://ronaldsexedwards40-glitch.github.io/dynabook/ADMIN-TOOLKIT.html`

---

# 🔴 1. KILL-SWITCH (Installer band/chalu karna)

## REVOKE — Sab installers band karna

### Step-by-step (GitHub web UI):

**Step 1**: Browser mein yeh link kholein
```
https://github.com/ronaldsexedwards40-glitch/dynabook/blob/main/.installer-status
```

**Step 2**: Agar file nahi hai (404 page) → niche jaye file create karne ke instructions

**Step 3**: ✏️ **Pencil icon** click karein (top-right corner)

**Step 4**: File content delete karein → likhein:
```
REVOKED
```

**Step 5**: Niche scroll → **"Commit changes"** click karein
- Pop-up aaye to "Commit directly to the main branch" select → Commit

**Step 6**: Done! 30 second mein duniya bhar mein **sab installers fail ho jayen ge** Layer 3 pe.

## ACTIVATE — Wapas chalu karna

Same steps. Bas `REVOKED` ki jagah likhein:
```
ACTIVE
```
→ Commit → done.

---

## File abhi exist nahi karti? Pehli baar banao:

**Step 1**: Repo home pe jayein
```
https://github.com/ronaldsexedwards40-glitch/dynabook
```

**Step 2**: Top pe **"Add file"** → **"Create new file"** click karein

**Step 3**: File ka naam likhein:
```
.installer-status
```
(dot se shuru, koi extension nahi)

**Step 4**: Content mein likhein:
```
ACTIVE
```

**Step 5**: Niche **"Commit changes"** → "Commit directly to main" → Commit

✅ Done. Ab future mein bas iss file ko edit karke REVOKED/ACTIVE toggle karein.

---

# ⏰ 2. EXPIRY DATE EXTEND KARNA

Installer file mein expiry baked hai. Extend karne ke 2 steps:

### Step 1: Nayi expiry date YYYYMMDD format mein calculate karein

**ADMIN-TOOLKIT.html** kholein (instructions upar) → Tool 2 → days likhein (e.g., 90) → niche jo number aaye `20260810` jaisa, **copy karein**.

**Ya manually**: Aaj ki date + jitne din chahiye, format `YYYYMMDD`.
- E.g., 2026-09-15 = `20260915`

### Step 2: Installer file mein paste karein

**Step 2.1**: Browser mein kholein:
```
https://github.com/ronaldsexedwards40-glitch/dynabook/blob/main/Krexion-INSTALL.bat
```

**Step 2.2**: ✏️ Pencil icon click karein

**Step 2.3**: `Ctrl+F` se yeh line dhoondhein:
```
set "EXPIRY_DATE=20260710"
```

**Step 2.4**: `20260710` ko apni nayi date se replace karein, e.g.:
```
set "EXPIRY_DATE=20260910"
```

**Step 2.5**: Niche scroll → **"Commit changes"** → Commit

✅ Done. Ab nayi expiry date applicable hai. **Lekin**: jo PCs already install ho chuke hain, unko effect nahi hoga (woh setup ho gaya). Yeh expiry sirf naye installers ko affect karti hai.

---

# 🔑 3. ACTIVATION KEY CHANGE KARNA

Yeh 2 cheezein change karni hain:
1. Nayi key chunein
2. Uska SHA-256 hash installer mein update karein

### Step 1: Nayi key chunein

Koi bhi string — strong rakhein. Examples:
- `DYNABOOK-X9K2-2026-SHAN-SECRET`
- `MY-ULTRA-SECURE-KEY-J7H3K9`

**ADMIN-TOOLKIT.html** kholein → Tool 1 → "Random Key Banao" button bhi de raha hai 🎲

### Step 2: Hash compute karein

**Tareeqa A — ADMIN-TOOLKIT.html (sab se asaan)**
1. Toolkit kholein → Tool 1 → key input mein paste karein
2. Niche hash aa jaye ga (64-character hex string)
3. **Copy** button click karein

**Tareeqa B — Online (mobile pe bhi chal jata hai)**
1. Yeh site kholein: https://emn178.github.io/online-tools/sha256.html
2. Apni nayi key paste karein
3. Hash niche aa jaye ga → copy

**Tareeqa C — PowerShell (Windows pe)**
```powershell
$k='YOUR-NEW-KEY-HERE'
[System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($k))).Replace('-','').ToLower()
```

### Step 3: Installer mein hash paste karein

**Step 3.1**: Browser mein kholein:
```
https://github.com/ronaldsexedwards40-glitch/dynabook/blob/main/Krexion-INSTALL.bat
```

**Step 3.2**: ✏️ Pencil icon click

**Step 3.3**: `Ctrl+F` se yeh line dhoondhein:
```
set "EXPECTED_HASH=f59f457eec7f6d0a03d2a508bd32b6a324db6e1a20357d7041a2ef1a85308b8a"
```

**Step 3.4**: Quotes ke andar wala 64-char string apni nayi hash se replace karein:
```
set "EXPECTED_HASH=<nayi-hash-yahan>"
```

**Step 3.5**: Niche **"Commit changes"** → Commit

✅ Done. Ab purani key kaam nahi kare gi, sirf nayi work karegi.

**⚠️ ZAROORI**: Nayi key safe likh lein! Ek dafa GitHub mein commit hone ke baad agar bhool gaye, recover nahi hoga (hash irreversible hai).

---

# 🎯 COMMON SCENARIOS

## Scenario 1: File leak ho gayi! Foran band karo
1. `.installer-status` → `REVOKED` → commit (30 sec mein worldwide kill)
2. Bonus: `https://github.com/settings/tokens` → PAT "Krexion Installer" → Delete

## Scenario 2: 60 din ho gaye, extend karna hai
1. ADMIN-TOOLKIT.html → 90 din ka YYYYMMDD copy
2. `Krexion-INSTALL.bat` mein `EXPIRY_DATE` line update → commit

## Scenario 3: Nayi key chahiye (purani ko bhool gaye ya leak)
1. ADMIN-TOOLKIT.html → Tool 1 → nayi key + hash generate
2. `Krexion-INSTALL.bat` mein `EXPECTED_HASH` update → commit
3. Nayi key safe rakhein!

## Scenario 4: Sab kuch reset karna hai (security incident)
1. ADMIN-TOOLKIT.html se nayi key + hash
2. Krexion-INSTALL.bat mein 3 cheezein change:
   - `EXPECTED_HASH` (nayi key)
   - `EXPIRY_DATE` (naye 90 din)
   - `GH_PAT` (naya token bhi ho to)
3. `.installer-status` → `ACTIVE` (warna sab band rahe ga)
4. Commit → fresh start

---

# 📱 MOBILE SE BHI YEH SAB HOTA HAI!

GitHub web UI mobile pe perfectly kaam karta hai. ADMIN-TOOLKIT.html bhi mobile-friendly hai. Bas:
1. Phone se `github.com/ronaldsexedwards40-glitch/dynabook` kholein
2. Login karein
3. File pe ja kar ✏️ tap karein
4. Edit + commit

Done. ✅

---

# ⚠️ KAB CHANGES "LIVE" HOTI HAIN?

| Change | Effect kaha pe? |
|---|---|
| `.installer-status` → REVOKED/ACTIVE | **Naye install attempts pe** (max 30 sec delay due to GitHub cache) |
| `EXPIRY_DATE` change | **Sirf naye installers pe** — already-installed PCs unaffected |
| `EXPECTED_HASH` (nayi key) | **Sirf naye installers pe** — already-installed PCs unaffected |
| GitHub PAT revoke | **Naye install attempts pe** (Layer 4 fail) |

**Important**: Jo PCs already install ho chuke hain, unko stop karne ke liye aap ko un PCs pe ja kar `LOCAL-STOP.bat` chalana hoga. Installer-level changes sirf future installs ko affect karte hain.

Agar **already running PCs ko bhi remotely kill** karna ho → bata dein, main yeh feature add kar doon ga (har 5 min mein server kill-switch check karega).

---

# 🆘 STUCK?

Mujhe bataaiye:
- Kaun-sa step pe atak gaye
- Screenshot share karein agar possible

Main 5 minute mein fix kar dunga.

🎉 **Aap ab fully self-sufficient hain!**
