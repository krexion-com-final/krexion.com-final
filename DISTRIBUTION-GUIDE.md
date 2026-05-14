# 📦 Distribution Guide — Konsi File Kis Ko Dein

## 🎯 2 Tarah Ki Files Hain Ab

| File | Kiske Liye | Kya Karta Hai |
|------|------------|---------------|
| `REALFLOW.bat` | **Aap (Admin)** | Admin password show karta hai — aap kar sakte ho license issue, user manage, etc |
| `REALFLOW-CUSTOMER.bat` | **Customer** | Admin password HIDE — customer sirf normal user account banata hai |

## 🔐 Kya Farq Hai?

### REALFLOW.bat (Admin Version)
- ✅ Install ke baad **admin password Desktop pe save** hota hai
- ✅ Aap `/admin-login` se login kar sakte hain
- ✅ License management, user approval, pricing control
- ✅ Browser khulta hai → `http://localhost:3000`

### REALFLOW-CUSTOMER.bat (Customer Version)
- ❌ Admin password **kahin save nahi hota** — customer ko pata hi nahi chalega
- ✅ Customer ko `/register` page pe direct le jata hai
- ✅ Customer apna naam/email se naya account banata hai
- ✅ License key aap se WhatsApp pe leta hai
- ✅ Browser khulta hai → `http://localhost:3000/register`
- ✅ `.env` mein `IS_CUSTOMER_INSTALL=true` set hota hai (future code-level admin lock ke liye)

## 📤 Customer Ko Kya Bhejen

### Option 1: ZIP Bhejen (Best)

GitHub se ZIP download karein aur customer ko bhejein. Customer ko bolen:

```
🚀 RealFlow Install:

1. ZIP file download karein
2. Extract karein (Desktop pe acha hai)
3. "REALFLOW-CUSTOMER.bat" file dhondein (REALFLOW.bat NAHI!)
4. Us pe double-click karein
5. UAC popup pe "YES"
6. 20-30 minute wait karein

Browser khulega → Register page → naya account banayein.

License key chahiye to mujhe WhatsApp karein.
```

### Option 2: Sirf 2 Files Bhejen

WhatsApp pe ZIP karke bhejen:
- `REALFLOW-CUSTOMER.bat` (3 KB)
- `install-master.ps1` (22 KB)

Customer extract karke `REALFLOW-CUSTOMER.bat` double-click kare.

## 🚨 Important: Customer Ko REALFLOW.bat NAHI Bhejna!

Agar customer ne **REALFLOW.bat** chala diya:
- Admin password Desktop pe save ho jata hai (`RealFlow-Info.txt`)
- Customer use kar sakta hai `/admin-login`
- Customer sab kuch control kar sakta hai

**Hamesha `REALFLOW-CUSTOMER.bat` ZIP mein dalein.**

## 📋 Workflow

```
┌─────────────────────────────────────────────────────────┐
│ AAP (ADMIN)                                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. REALFLOW.bat se apni PC pe install                 │
│  2. Admin panel access (admin@realflow.local)          │
│  3. /admin/licenses pe pricing/rules set karein        │
│                                                         │
│  Apni PC: http://localhost:3000/admin-login            │
│                                                         │
└─────────────────────────────────────────────────────────┘
                          ↓
          Customer aap se contact kare
                          ↓
┌─────────────────────────────────────────────────────────┐
│ CUSTOMER                                                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Aap se REALFLOW-CUSTOMER.bat le                    │
│  2. Apni PC pe install                                  │
│  3. /register pe account banaye                         │
│  4. Aap se license key WhatsApp se le                  │
│  5. Setup wizard mein activate                         │
│                                                         │
│  Customer PC: http://localhost:3000                    │
│  (admin URL pata hi nahi chalega)                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 💡 Customer Activation Process

### Phase 1: Customer Install (20-30 min)
1. Customer `REALFLOW-CUSTOMER.bat` chalata hai
2. Install complete hote hi `/register` page khul jati hai

### Phase 2: Account Create (2 min)
1. Customer apna naam, email, password daalta hai
2. Account ban jata hai (status: pending)

### Phase 3: License Issue (Aap karte hain, 1 min)
1. Customer aap ko WhatsApp karega "Account ban gaya, license chahiye"
2. Aap admin panel mein `/admin/licenses` kholein
3. **"Issue Manual License"** button
4. Customer ka email + days (e.g., 30 days)
5. License key generate hoti hai
6. Customer ko WhatsApp pe key send karein

### Phase 4: Activate (Customer karta hai, 1 min)
1. Customer setup wizard mein "I have a license key" click karega
2. Key paste karega
3. Activate
4. ✅ RealFlow chalu

### Phase 5: Login (Customer karta hai)
1. Customer `/login` page pe email + password daalta hai
2. Dashboard khulta hai
3. Use karna start kar deta hai

## 🆘 Common Customer Questions

### "Admin login button kahan hai?"
Customer ko bata den: "Aap ko admin login ki zaroorat nahi. Aap `/login` use karein." (Admin URL bohot zaroori ho to console mein `http://localhost:3000/admin-login` type karein — but customer ko password nahi pata so wo login nahi kar payega)

### "Mein admin password kahan dhondun?"
"Customer install mein admin password generate nahi hota. Aap apna user account `/register` se banayein."

### "Kya mein khud admin ban sakta hun?"
"Nahi, admin = business owner role. Aap regular user hain. Lekin aap apne dashboard mein sab features use kar sakte hain."

## 🔒 Extra Security (Optional Future Enhancement)

Agar aap chahein to backend mein bhi block kar sakte hain:

```python
# server.py mein add karein:
IS_CUSTOMER = os.environ.get('IS_CUSTOMER_INSTALL', 'false').lower() == 'true'

@app.middleware("http")
async def block_admin_in_customer_mode(request, call_next):
    if IS_CUSTOMER and request.url.path.startswith("/api/admin/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return await call_next(request)
```

Yeh customer mode mein **/api/admin/*** endpoints completely block kar dega — chahe customer admin password pata bhi le, login nahi kar payega.

Bata den agar yeh add karna hai!

## ✅ Final Distribution Checklist

Customer ko bhejne se pehle:
- [ ] **Save to GitHub** button click ho gaya
- [ ] **REALFLOW-CUSTOMER.bat** file mein hai
- [ ] **install-master.ps1** saath hai
- [ ] Customer ko **admin password** kahin se nahi pata
- [ ] License key issue karne ka plan hai

## 🎯 Quick Reference

```
Aap install karein:        REALFLOW.bat       (admin access milta hai)
Customer install karein:   REALFLOW-CUSTOMER.bat (sirf user features)
```

Bas itna hi! Customer ko `REALFLOW-CUSTOMER.bat` bhejein, baki same workflow.
