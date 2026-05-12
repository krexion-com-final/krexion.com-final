================================================================
   REALFLOW CPI WORKER - PEHLE PARHEIN (Roman Urdu Guide)
================================================================

Ye guide aap ke liye hai - bohat aasan hai. Sirf 4 steps mein kaam ho jayega.

----------------------------------------------------------------
ZARURI CHEEZEN (Pehli baar)
----------------------------------------------------------------

[A] PC par Python 3.10 ya newer install hona chahiye
    Download: https://www.python.org/downloads/
    INSTALL ke waqt "Add Python to PATH" check karein (sab se important!)

[B] Phone par Developer Options aur USB Debugging ON hona chahiye
    Phone Settings > About Phone > Build Number par 7 baar tap karein
    (Developer mode unlock ho jayega)
    Phir Settings > Developer Options > "USB Debugging" ON karein

[C] DATA USB cable (charging-only cable se kaam nahi karega)

[D] Internet connection - bridge auto-download ke liye

----------------------------------------------------------------
4 STEPS - WORKER START KARNE KA TARIQA
----------------------------------------------------------------

STEP 1:  USB cable se phone PC se connect karein
         Phone unlock rakhein

STEP 2:  Is folder mein "START-CPI.bat" file double-click karein
         Pehli baar setup ho raha hai to 2-3 mint lagengae:
            - ADB auto-download (50 MB)
            - Python packages install
            - Notepad mein config.yaml khulega - aap ka token paste karein

STEP 3:  Token paste karne ka tareeqa:
         a. Browser mein https://realflow.online kholein
         b. Login karein:  admin@realflow.local / admin123
         c. F12 dabayein (DevTools khulega)
         d. "Application" tab > Local Storage > https://realflow.online
         e. "token" naam ki entry dhundhein - uski lambi value copy karein
         f. Notepad mein "PASTE_YOUR_REALFLOW_JWT_HERE" replace karein
            (token paste karein, baki kuch na chedhein)
         g. Ctrl+S (save) > close

STEP 4:  Web UI mein job banayein aur start karein:
         a. https://realflow.online > CPI module
         b. New Job:
              - Offer URL: aap ka real tracker URL
              - Proxy: Japan Proxy Jet
              - User Agent: Japan Android UA  
              - Target count: 1 (test ke liye)
         c. "Start Job" dabayein

         Worker terminal mein automatic logs ayenge:
            click_tracker_serverside (status=200)
            apk_resolved
            install (OK)
            auto_dismiss_popups
            permissions_granted
            behavior_sim
            settle

----------------------------------------------------------------
COMMON PROBLEMS aur FIX
----------------------------------------------------------------

[Problem 1] "Phone offline a raha hai"
            FIX: "FIX-PHONE.bat" double-click karein - guided steps milengi.

[Problem 2] "Phone unauthorized"
            Phone par "Allow USB debugging" popup pe "Always allow" CHECK karein

[Problem 3] "ADB auto-download fail"
            Manual download: 
            https://dl.google.com/android/repository/platform-tools-latest-windows.zip
            ZIP extract karein - "platform-tools" folder is .bat ke saath rakhein

[Problem 4] "Token paste karne ke baad bhi error"
            Token complete copy karein (lambi string hoti hai - 200+ characters)
            config.yaml mein quotes mein paste karein:
              token: "yahan_token_paste_karein"

[Problem 5] "Click_failed_http_xxx"
            Proxy Jet credentials check karein (expired ho sakte hain)
            Web UI mein job ka proxy change karke retry karein

[Problem 6] "No work" - worker chal raha hai par job nahi mil rahi
            Web UI mein job "Active" status mein hai check karein
            Worker terminal mein device "online" hai check karein

----------------------------------------------------------------
3 FILES IS FOLDER MEIN
----------------------------------------------------------------

  START-CPI.bat       <- YEHI double-click karna hai (master launcher)
  FIX-PHONE.bat       <- Sirf phone offline issue ke liye
  README-PEHLE-PARHEIN.txt  <- Ye file (guide)

----------------------------------------------------------------
KOI PROBLEM HO TO
----------------------------------------------------------------

1. Worker terminal ka FULL screenshot lekar bhejein
2. Phone ki screen ka screenshot bhejein
3. Web UI ka job page ka screenshot bhejein

Tinno screenshots se main turant fix kar sakta hun.

ALL THE BEST! - RealFlow Team
================================================================
