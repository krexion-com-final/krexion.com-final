# Krexion — Customer ko Globally Online Karne Ka Tareeqa

## Aapke Customer Ka Problem
> "Krexion mere ghar/office ke PC pe install hai. Main bahar gaya hu — mobile pe app kaise kholun?"

## Solution: GO-ONLINE.bat (One Click)

Customer ko sirf **2 files** chahiye:
- `GO-ONLINE.bat`
- `GO-ONLINE.ps1`

Customer ke desktop par rakho. Bas.

---

## Customer Ka Step-by-Step Process

### Setup (Pehli Baar Sirf — 1 minute):
1. **GO-ONLINE.bat** aur **GO-ONLINE.ps1** Desktop pe save karo (ya kahin bhi same folder mein)
2. Bas. Setup khatam.

### Daily Use (Har Baar Online Karne Ke Liye):

**Step 1**: PC pe Krexion chalu hai? Check karo:
- Browser kholo → `http://localhost:3000`
- Agar khulta hai → ready ho
- Agar nahi → Docker Desktop start karo → 1 min wait → wapas try karo

**Step 2**: `GO-ONLINE.bat` pe **double-click**

**Step 3**: 30 second wait — pehli baar cloudflared.exe download hoga (~25 MB, one-time)

**Step 4**: Naya browser window khulega khud:
```
+--------------------------------------------------+
|   LIVE -- ONLINE NOW                             |
|                                                   |
|   Your Krexion is online                        |
|                                                   |
|   https://blue-fox-42.trycloudflare.com  [Copy]  |
|                                                   |
|   [QR Code]      [Open Now]                      |
|                  [Share on WhatsApp]              |
|                                                   |
|   Keep this window open. Tunnel stays as long    |
|   as the console window is open.                 |
+--------------------------------------------------+
```

**Step 5**: Ye URL share karo:
- **Khud ke mobile** pe — QR code scan karo
- **Customer ko** — Copy button → WhatsApp pe paste
- **Team members** — Share on WhatsApp button

**Step 6**: Mobile par URL kholo → app khulegi exactly jaise PC par.

---

## Important Rules

### ✅ DO:
- Console window khula chhod do (background mein chalne do)
- Browser tab ko taskbar pe minimize kar sakte ho
- Use the app from mobile/laptop normally
- Done ho jane par window close karo (tunnel band ho jayega)

### ❌ DON'T:
- Console window **close mat karo** jab tak online rakhna hai
- PC band mat karo (Krexion band ho jayega)
- Bhool kar `Ctrl+C` mat dabao (tunnel break ho jayega)
- Hibernate/Sleep mat hone do PC ko

---

## Limitations (Kya Cheezein Yaad Rakhni Hain)

### 🟡 URL temporary hai
Har baar `GO-ONLINE.bat` chalane par **naya URL** banta hai:
- Pehli baar: `blue-fox-42.trycloudflare.com`
- Doosri baar: `red-cat-77.trycloudflare.com`

**Solution**: Har baar URL share karna padega.

**Permanent URL chahiye?** → Cloudflare named tunnel + own domain (advanced)

### 🟡 PC ON hona chahiye
Tunnel ka matlab "PC ka shortcut internet pe" — agar PC band ho:
- App offline ho jati hai
- URL "Bad Gateway" dikhayegi

**Solution**:
- PC ko power settings mein "Never Sleep" karo
- Hibernate disable karo
- 24/7 chalane ho to **cloud pe move karo** (Krexion Render deploy guide dekho)

### 🟡 Speed limit
Tunnel free hai lekin bandwidth share hoti hai:
- Normal browsing: fast
- Heavy load (100+ concurrent users): slow ho sakti hai

---

## Common Errors + Fixes

### Error: "Krexion is NOT running on this PC"
**Cause**: Docker containers band hain
**Fix**:
1. Docker Desktop kholo (Start menu → search Docker)
2. Whale icon steady hone ka wait karo
3. Command Prompt kholo:
   ```
   cd C:\krexion
   docker compose up -d
   ```
4. 30 sec wait → wapas `GO-ONLINE.bat` chalao

### Error: "Could not download cloudflared.exe"
**Cause**: Internet ya firewall issue
**Fix**:
1. WiFi check karo
2. https://github.com pe browser mein jao — agar nahi khulta → ISP firewall
3. VPN use karo
4. Manual: https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe download karo, GO-ONLINE.bat ke same folder mein "cloudflared.exe" name se save karo, phir try karo

### Error: "Could not get a public URL from Cloudflare after 90 seconds"
**Cause**: Cloudflare ko reach nahi kar pa raha
**Fix**:
1. Mobile hotspot try karo (alag network)
2. VPN off karo (kabhi VPN tunnel pe rok deta hai)
3. Antivirus check karo (Avast/McAfee kabhi block kar dete hain)

### Error: "Tunnel ended unexpectedly"
**Cause**: Network disconnect ya cloudflared crash
**Fix**: Bas dobara `GO-ONLINE.bat` chala do — naya URL mil jayega

---

## Multi-Device Workflow Example

### Scenario:
- Customer ka PC: **ghar mein** (Krexion install)
- Customer ka mobile: **office mein**
- Customer ki laptop: **dost ke ghar**

### Setup:
1. Subah customer ghar se nikalne se pehle:
   - PC pe Docker Desktop khula chhoda
   - `GO-ONLINE.bat` double-click kiya
   - URL apne mobile mein bookmark kiya
2. Mobile pe office mein:
   - Bookmark se URL kholi → app khuli → kaam kiya
3. Laptop dost ke ghar:
   - Mobile se URL copy karke WhatsApp pe self-message kiya
   - Laptop pe WhatsApp Web → URL kholi → kaam jari rakha
4. Raat ko ghar wapas:
   - Console window close kiya → tunnel band → secure

**Same URL** sab devices pe kaam karta hai jab tak console open hai.

---

## Security Tips

### Aapki URL random hoti hai:
- 8-character random subdomain
- Brute-force ke liye guess karna almost impossible
- Sirf jisko URL share karenge wahi access kar sakta hai

### Lekin ek baar share ki to:
- Jisko URL pata hai woh login screen tak pohnch jayega
- Phir Krexion ka apna admin/user login (email + password) protect karega
- Agar koi password leak ho jaye → Krexion admin se password reset karwao

### Best practice:
- URL **trusted log ko hi share** karo (apne aap ko, team members ko)
- Strong Krexion passwords use karo
- Done ho jane par console close karo

---

## Quick Reference Card (Customer ko bhejne ke liye)

```
+================================================+
|   Krexion GO ONLINE -- Quick Card             |
+================================================+
|                                                 |
|   STEP 1: Open Docker Desktop, wait 1 min      |
|   STEP 2: Double-click GO-ONLINE.bat           |
|   STEP 3: Browser window opens with URL        |
|   STEP 4: Copy URL or scan QR -> use on mobile|
|   STEP 5: Done ho jane par window close karo   |
|                                                 |
|   PROBLEM HO TO: GO-ONLINE-CUSTOMER-GUIDE.md   |
|                  dekho ya admin ko call karo   |
+================================================+
```

---

## Want Permanent URL? (Upgrade Path)

Free `trycloudflare.com` URL har baar change hota hai. Permanent professional URL chahiye?

### Option A: Aap ke admin URL ko share karo (Cloud Deploy)
1. Aap khud Render deploy karo (`ADMIN-URL-SETUP.md` dekho)
2. Customer ke liye account create karo cloud version pe
3. Customer ko sirf cloud URL do — woh kahin se bhi use karega
4. PC dependency khatam

### Option B: Customer ka apna Cloudflare named tunnel
1. Customer Cloudflare account banaye
2. Customer domain khareeda ($10/year)
3. Named tunnel setup (1-time, 10 min)
4. Same `krexion-ahmad.online` URL hamesha kaam kare

---

## Summary

| Cheez | GO-ONLINE.bat (yeh) | Cloud Deploy (Render) |
|-------|---------------------|----------------------|
| Setup | Free, 1 minute | Free, 15 minute |
| URL | Temporary | Permanent |
| PC requirement | ON honi chahiye | Not needed |
| Speed | Customer ke internet pe depend | Datacenter (fast) |
| Best for | Demo, testing, personal use | Production, real customers |
| Cost | $0 forever | $0-$7/mo |

**Recommendation**:
- **Aapke personal admin use ke liye** → Cloud Deploy (Render) — permanent URL
- **Customer ke local PC use ke liye** → GO-ONLINE.bat — when they want mobile access
