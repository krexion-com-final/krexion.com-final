"""Android fingerprint randomization — GAID, Android ID, build.prop, IMEI, MAC."""
from __future__ import annotations

import logging
import random
import string
import uuid
from typing import Dict, Optional

logger = logging.getLogger("cpi.fingerprint")

# Real device profiles — ARM/Android only. Each install picks one at random.
# Trimmed sample; expand by appending more entries from a fingerprint database.
DEVICE_PROFILES = [
    {
        "manufacturer": "samsung", "brand": "samsung", "model": "SM-A515F",
        "product": "a51nseea", "device": "a51", "board": "exynos9611",
        "fingerprint": "samsung/a51nseea/a51:13/TP1A.220624.014/A515FXXSEHWE2:user/release-keys",
        "android_release": "13", "sdk": "33", "build_id": "TP1A.220624.014",
    },
    {
        "manufacturer": "Xiaomi", "brand": "Redmi", "model": "M2010J19SG",
        "product": "lime_global", "device": "lime", "board": "mt6769v_ct",
        "fingerprint": "Redmi/lime_global/lime:11/RP1A.200720.011/V12.5.13.0.RJOMIXM:user/release-keys",
        "android_release": "11", "sdk": "30", "build_id": "RP1A.200720.011",
    },
    {
        "manufacturer": "OPPO", "brand": "OPPO", "model": "CPH2127",
        "product": "CPH2127", "device": "OP4F69L1", "board": "msm8953",
        "fingerprint": "OPPO/CPH2127/OP4F69L1:11/RKQ1.211103.002/1648708870:user/release-keys",
        "android_release": "11", "sdk": "30", "build_id": "RKQ1.211103.002",
    },
    {
        "manufacturer": "Google", "brand": "google", "model": "Pixel 6a",
        "product": "bluejay", "device": "bluejay", "board": "bluejay",
        "fingerprint": "google/bluejay/bluejay:13/TQ3A.230805.001/10316531:user/release-keys",
        "android_release": "13", "sdk": "33", "build_id": "TQ3A.230805.001",
    },
    {
        "manufacturer": "vivo", "brand": "vivo", "model": "V2025",
        "product": "PD2050F_EX", "device": "PD2050F_EX", "board": "PD2050",
        "fingerprint": "vivo/PD2050F_EX/PD2050F_EX:11/RP1A.200720.012/compiler11030712:user/release-keys",
        "android_release": "11", "sdk": "30", "build_id": "RP1A.200720.012",
    },
    {
        "manufacturer": "realme", "brand": "realme", "model": "RMX3263",
        "product": "RMX3263", "device": "RE54B5L1", "board": "QM215",
        "fingerprint": "realme/RMX3263/RE54B5L1:11/RKQ1.201217.002/S.b75e7-39d72:user/release-keys",
        "android_release": "11", "sdk": "30", "build_id": "RKQ1.201217.002",
    },
]


def random_gaid() -> str:
    return str(uuid.uuid4())


def random_android_id() -> str:
    return "".join(random.choices("0123456789abcdef", k=16))


def random_imei() -> str:
    """14 random digits + Luhn check digit."""
    digits = [random.randint(0, 9) for _ in range(14)]
    s = 0
    for i, d in enumerate(digits):
        if i % 2 == 0:
            s += d
        else:
            x = d * 2
            s += x if x < 10 else (x - 9)
    check = (10 - (s % 10)) % 10
    return "".join(str(d) for d in digits) + str(check)


def random_mac() -> str:
    return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))


def random_serial(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def pick_profile() -> Dict[str, str]:
    return dict(random.choice(DEVICE_PROFILES))


def geo_to_locale(geo_iso2: Optional[str]) -> Dict[str, str]:
    """Map geo ISO-2 to a representative locale + timezone + GPS coordinates."""
    geo = (geo_iso2 or "US").upper()
    table = {
        "US": ("en-US", "America/New_York", "40.7128", "-74.0060"),
        "UK": ("en-GB", "Europe/London", "51.5074", "-0.1278"),
        "GB": ("en-GB", "Europe/London", "51.5074", "-0.1278"),
        "CA": ("en-CA", "America/Toronto", "43.6532", "-79.3832"),
        "AU": ("en-AU", "Australia/Sydney", "-33.8688", "151.2093"),
        "DE": ("de-DE", "Europe/Berlin", "52.5200", "13.4050"),
        "FR": ("fr-FR", "Europe/Paris", "48.8566", "2.3522"),
        "ES": ("es-ES", "Europe/Madrid", "40.4168", "-3.7038"),
        "IT": ("it-IT", "Europe/Rome", "41.9028", "12.4964"),
        "NL": ("nl-NL", "Europe/Amsterdam", "52.3676", "4.9041"),
        "PL": ("pl-PL", "Europe/Warsaw", "52.2297", "21.0122"),
        "PK": ("en-PK", "Asia/Karachi", "24.8607", "67.0011"),
        "IN": ("en-IN", "Asia/Kolkata", "28.6139", "77.2090"),
        "ID": ("id-ID", "Asia/Jakarta", "-6.2088", "106.8456"),
        "PH": ("en-PH", "Asia/Manila", "14.5995", "120.9842"),
        "BR": ("pt-BR", "America/Sao_Paulo", "-23.5505", "-46.6333"),
        "MX": ("es-MX", "America/Mexico_City", "19.4326", "-99.1332"),
        "AR": ("es-AR", "America/Argentina/Buenos_Aires", "-34.6037", "-58.3816"),
        "JP": ("ja-JP", "Asia/Tokyo", "35.6762", "139.6503"),
        "KR": ("ko-KR", "Asia/Seoul", "37.5665", "126.9780"),
        "TR": ("tr-TR", "Europe/Istanbul", "41.0082", "28.9784"),
        "RU": ("ru-RU", "Europe/Moscow", "55.7558", "37.6173"),
        "CN": ("zh-CN", "Asia/Shanghai", "31.2304", "121.4737"),
        "TH": ("th-TH", "Asia/Bangkok", "13.7563", "100.5018"),
        "VN": ("vi-VN", "Asia/Ho_Chi_Minh", "10.8231", "106.6297"),
    }
    locale, tz, lat, lng = table.get(geo, ("en-US", "America/New_York", "40.7128", "-74.0060"))
    # Add a little jitter to GPS so it's not the exact same coords every install
    import random as _r
    lat_j = float(lat) + _r.uniform(-0.05, 0.05)
    lng_j = float(lng) + _r.uniform(-0.05, 0.05)
    return {
        "locale": locale,
        "timezone": tz,
        "country": geo,
        "lat": f"{lat_j:.6f}",
        "lng": f"{lng_j:.6f}",
    }


def make_fingerprint(geo: Optional[str] = None) -> Dict[str, str]:
    profile = pick_profile()
    locale = geo_to_locale(geo)
    return {
        "gaid": random_gaid(),
        "android_id": random_android_id(),
        "imei": random_imei(),
        "wifi_mac": random_mac(),
        "bt_mac": random_mac(),
        "serial": random_serial(),
        **profile,
        **locale,
    }
