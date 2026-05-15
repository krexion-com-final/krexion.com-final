#!/bin/bash
# Krexion Live Google Sheet Diagnostic Script
# Run this on your production server (WSL / Linux container shell):
#   docker exec -it krexion-backend bash -c "$(cat diagnose_gsheet.sh)"
# OR if you have shell access on the host:
#   bash diagnose_gsheet.sh

echo "==================================================="
echo "1. Service Account JSON file check"
echo "==================================================="
SA_PATH="${GOOGLE_SHEETS_SA_PATH:-/app/backend/secrets/gsheets-sa.json}"
if [ -f "$SA_PATH" ]; then
    echo "✅ SA file found at: $SA_PATH"
    echo "   Size: $(wc -c < "$SA_PATH") bytes"
    echo "   client_email: $(grep -o '"client_email": "[^"]*"' "$SA_PATH" | head -1)"
else
    echo "❌ SA file MISSING at: $SA_PATH"
    echo "   You need to copy /app/backend/secrets/gsheets-sa.json from preview pod to your production server."
fi

echo
echo "==================================================="
echo "2. Environment variable check"
echo "==================================================="
echo "GOOGLE_SHEETS_SA_PATH = ${GOOGLE_SHEETS_SA_PATH:-(not set)}"
echo "GOOGLE_SHEETS_SA_JSON length = ${#GOOGLE_SHEETS_SA_JSON}"
if [ -z "$GOOGLE_SHEETS_SA_PATH" ] && [ -z "$GOOGLE_SHEETS_SA_JSON" ]; then
    echo "❌ NEITHER env var is set — gsheet_writer.is_write_enabled() will return False"
    echo "   Add to your /app/backend/.env on production:"
    echo "   GOOGLE_SHEETS_SA_PATH=/app/backend/secrets/gsheets-sa.json"
fi

echo
echo "==================================================="
echo "3. Live SA test (gsheet_writer module)"
echo "==================================================="
cd /app/backend 2>/dev/null
python3 -c "
import sys
sys.path.insert(0, '/app/backend')
try:
    from dotenv import load_dotenv
    load_dotenv('/app/backend/.env')
except Exception:
    pass
try:
    import gsheet_writer
    enabled = gsheet_writer.is_write_enabled()
    print(f'is_write_enabled() = {enabled}')
    if enabled:
        # Try to list tabs of the user's actual sheet
        url = 'https://docs.google.com/spreadsheets/d/1HjxVWDyQUgqBkRt_uds7s5wM9Sk3PNqPPJEzXFuzIfU/edit'
        tabs = gsheet_writer.list_tabs(url)
        print(f'Tabs in your sheet: {len(tabs)}')
        for t in tabs[:5]:
            print(f'   - {t[\"title\"]} ({t[\"row_count\"]} rows)')
        if not tabs:
            print('   ⚠️  ZERO tabs returned. Likely SA is loaded but the sheet is NOT shared as Editor.')
            print('       Open your sheet → Share → add: krexion-bot@rpa-data-test.iam.gserviceaccount.com → Editor')
    else:
        print('❌ gsheet_writer is NOT enabled. Check env vars + SA file path.')
except Exception as e:
    print(f'❌ Module error: {type(e).__name__}: {e}')
"

echo
echo "==================================================="
echo "4. Mongo: do your uploads have gsheet_url set?"
echo "==================================================="
MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"
echo "MONGO_URL: $MONGO_URL"
python3 -c "
import os, sys
from pymongo import MongoClient
url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = MongoClient(url)
# Find ALL user-scoped DBs
db_names = [d for d in client.list_database_names() if d.startswith('krexion_user_')]
print(f'Found {len(db_names)} user database(s)')
total_uploads = 0
gsheet_uploads = 0
non_gsheet_uploads = 0
for dbn in db_names:
    db = client[dbn]
    cur = db['uploaded_resources'].find({}, {'_id':0, 'id':1, 'name':1, 'type':1, 'gsheet_url':1, 'item_count':1, 'consumed_count':1})
    for u in cur:
        total_uploads += 1
        gurl = (u.get('gsheet_url') or '').strip()
        if gurl:
            gsheet_uploads += 1
            print(f'  ✅ [{u.get(\"type\"):10s}] {u.get(\"name\",\"\"):30s} item_count={u.get(\"item_count\",0):>6d} consumed={u.get(\"consumed_count\",0):>5d} GSHEET={gurl[:60]}')
        else:
            non_gsheet_uploads += 1
            print(f'  ⚠️  [{u.get(\"type\"):10s}] {u.get(\"name\",\"\"):30s} item_count={u.get(\"item_count\",0):>6d} (NO gsheet_url — static upload)')
print()
print(f'Total uploads: {total_uploads}')
print(f'  with gsheet_url:  {gsheet_uploads}  ← these will live-delete from sheet')
print(f'  without gsheet_url: {non_gsheet_uploads}  ← these are STATIC, will NOT delete from sheet')
"

echo
echo "==================================================="
echo "5. Backend log tail — look for live-delete attempts"
echo "==================================================="
echo "After running a RUT job, you should see lines like:"
echo "  INFO:server:gsheet live delete proxy: removed 1 row(s) from sheet"
echo "  INFO:server:gsheet live delete UA: removed 1 row(s) from sheet"
echo "If you see warnings instead, that tells you what's failing:"
echo "  WARNING:server:gsheet live delete proxy failed: HttpError 403 ..."
echo "    → SA email is NOT shared as Editor on the sheet"
echo "  WARNING:server:gsheet live delete proxy failed: ... write disabled ..."
echo "    → SA env var / file not set"
echo
echo "Recent backend log (last 30 lines, filtered):"
docker logs krexion-backend --tail 100 2>/dev/null | grep -iE "gsheet|live delete|sa_path|write_enabled" | tail -30 || \
  tail -n 100 /var/log/supervisor/backend.err.log 2>/dev/null | grep -iE "gsheet|live delete" | tail -30 || \
  echo "  (no matching log lines yet — run a small RUT job first, then check)"

echo
echo "==================================================="
echo "DIAGNOSIS COMPLETE"
echo "==================================================="
