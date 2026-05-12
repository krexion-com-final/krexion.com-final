web: uvicorn server:app --host 0.0.0.0 --port $PORT --workers ${UVICORN_WORKERS:-1} --timeout-keep-alive 30 --proxy-headers --forwarded-allow-ips '*'
