════════════════════════════════════════════════════════
                                                          
              KREXION                                    
              Install Karne Ka Tareeqa                    
                                                          
════════════════════════════════════════════════════════


PEHLI BAAR INSTALL KARNA HAI?
=================================

Bas 3 step:

  1. Yeh folder mein "INSTALL.bat" file dhondein
  
  2. Us file pe DOUBLE-CLICK karein

  3. UAC popup aaye to "YES" click karein

Bas! Phir 20-30 minute wait karein.
Sab kuch khud install ho jayega.

Browser khud khul jayegi.
Register page pe aap naya account banayein.



KYA HOTA HAI INSTALLATION KE DAURAN?
=====================================

  Console window khulegi (yeh band na karein!)
  
  Step 1: System check (10 second)
  Step 2: Windows features enable (1-3 min)
  Step 3: System engine update (1-2 min)
  Step 4: Krexion runtime install (5-10 min)
  Step 5: Engine start (1-5 min)
  Step 6: Krexion code download (1-2 min)
  Step 7: Containers build + start (5-15 min)
  
  TOTAL: 20-30 minute
  
  Aap coffee/chai piyen — sab automatic hai.



INSTALL KE BAAD KYA KARNA HAI?
================================

  1. Browser khud khulegi http://localhost:3000/register pe

  2. Apna naam, email, password daalein

  3. "Register" click karein

  4. Setup wizard khulega

  5. License key chahiye?
     - https://krexion.com/pricing par jaa kar USDT-TRC20 se khareedein
     - Plan select karein → wallet pe USDT bhejein → TxID submit karein
     - Verification ke baad license key email pe milegi (30 minute ke andar)
     - Wohi license key Krexion mein daal kar activate karein
     - Admin license key send karega
     - "I have a license key" click karein
     - Key paste karein
     - "Activate" click karein

  6. Login page pe email + password se login karein

  7. Dashboard khulega — bas! Use karna start karein.



MOBILE YA DOOSRI PC SE ACCESS KARNA HAI?
==========================================

  Install ke baad aap "C:\krexion" folder mein
  jayein aur "GO-ONLINE.bat" file double-click karein.

  Aap ko ek public URL milegi, jaise:
    https://abc-xyz-123.trycloudflare.com

  Yeh URL kahin se bhi access ho sakti hai:
    - Mobile pe URL kholein
    - Doosri PC pe URL kholein
    - QR code scan karein mobile se

  IMPORTANT: Console window band na karein! 
  Window band hone par URL dead ho jata hai.



DAILY USE KE FILES (C:\krexion folder mein)
==============================================

  LOCAL-START.bat       - Krexion start karne ke liye
  LOCAL-STOP.bat        - Krexion stop karne ke liye
  GO-ONLINE.bat         - Public URL banane ke liye
  KREXION-UPDATE.bat   - Latest version update ke liye
  KREXION-LOGS.bat     - Logs dekhne ke liye



PROBLEM AA RAHA HAI?
======================

  Pehle "FIX-PROBLEMS.bat" double-click karein!
  Yeh sab kuch khud diagnose aur fix karta hai.
  
  Installation kuch der ke baad stuck dikhe?
    - INTEZAR KAREIN! Heartbeat message dikhe to kaam chal raha hai
    - "wsl --update" 5-15 min le sakta hai (silent download)
    - "Krexion runtime download" 3-10 min le sakta hai
    - "Containers build" 5-15 min le sakta hai
    - Yeh sab NORMAL hai - 30 min tak wait karein
  
  Truly stuck ho gaya?
    - "FIX-PROBLEMS.bat" double-click karein
    - Wo khud sab fix karega
  
  Phir bhi issue?
    - Log files admin ko bhejen:
      C:\Users\YOUR-NAME\AppData\Local\Temp\krexion-install.log
      C:\Users\YOUR-NAME\AppData\Local\Temp\krexion-transcript.log
  
  Browser nahi khula?
    - Manually kholein: http://localhost:3000/register



SYSTEM REQUIREMENTS
=====================

  OS:       Windows 10 (build 19041+) ya Windows 11
  RAM:      8 GB minimum (16 GB recommended)
  Storage:  20 GB free space
  Internet: First-time install ke liye 5 Mbps minimum



════════════════════════════════════════════════════════
                                                          
  Mubarak ho! Yeh padhne ke baad aap ready hain.          
                                                          
  Bas INSTALL.bat double-click karein.                    
                                                          
════════════════════════════════════════════════════════
