"""
Screenshot verifier — perceptual hash similarity check.

Used to confirm a Real User Traffic visit ACTUALLY landed on the user's
expected final / thank-you page, not just *redirected* to a different
host (which our heuristics would otherwise count as a conversion).

Strategy: precompute a pHash of the user-uploaded target screenshot at
job creation. After every visit, take a screenshot of the final page
and compute the same pHash. Hamming distance ≤ `threshold` = match.

pHash vs other hashes:
  - dHash: fast but fragile against minor color shifts
  - aHash: too lenient — matches almost anything
  - pHash: robust to color, brightness, small layout shifts → best fit
    for affiliate-network thank-you pages whose colors/animations vary.

Hamming distance interpretation (using 8x8 default = 64-bit hash):
  0     identical
  1-6   very similar (basically same page)
  7-12  similar layout (different language / minor variant)
  13-22 same template, different content
  >22   different page
Default threshold = 12 — practical for affiliate networks where the same
thank-you template appears across visits with rotating offers/banners.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

logger = logging.getLogger("rut.shotverify")


def compute_phash(image_bytes: bytes) -> Optional[str]:
    """Return a hex pHash for the given image bytes, or None if invalid."""
    try:
        import imagehash
        from PIL import Image
        with Image.open(io.BytesIO(image_bytes)) as im:
            # Auto-orient + normalize to RGB so EXIF/transparency don't skew hash
            try:
                from PIL import ImageOps
                im = ImageOps.exif_transpose(im)
            except Exception:
                pass
            if im.mode != "RGB":
                im = im.convert("RGB")
            h = imagehash.phash(im, hash_size=8)
            return str(h)
    except Exception as e:
        logger.debug(f"compute_phash failed: {e}")
        return None


def compare_phashes(hash_a: str, hash_b: str) -> Optional[int]:
    """Return Hamming distance between two pHashes (0..64), or None on error."""
    if not hash_a or not hash_b:
        return None
    try:
        import imagehash
        ha = imagehash.hex_to_hash(hash_a)
        hb = imagehash.hex_to_hash(hash_b)
        return int(ha - hb)
    except Exception as e:
        logger.debug(f"compare_phashes failed: {e}")
        return None


def similarity_pct(distance: int, total_bits: int = 64) -> int:
    """Convert Hamming distance to a 0..100 similarity percentage."""
    if distance is None:
        return 0
    if distance < 0:
        distance = 0
    if distance > total_bits:
        distance = total_bits
    return int(round((1.0 - (distance / total_bits)) * 100))


def is_match(distance: int, threshold: int = 12) -> bool:
    """True if Hamming distance is within the configured similarity threshold."""
    if distance is None:
        return False
    return distance <= threshold
