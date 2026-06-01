"""
Supabase Storage service for Celestial Arc.
Handles palm image and kundli chart uploads/deletions via Supabase Storage.
Falls back to local filesystem if Supabase is not configured.

Buckets used:
  palm-images   — scanned palm photos
  kundli-images — user-uploaded Kundli chart images (private)
"""
import logging
import os
import uuid
from typing import Optional

logger = logging.getLogger(__name__)
_supabase_client = None
_supabase_init_attempted = False
_PALM_BUCKET = "palm-images"
_KUNDLI_BUCKET = "kundli-images"


def _get_supabase():
    global _supabase_client, _supabase_init_attempted
    if _supabase_init_attempted:
        return _supabase_client
    _supabase_init_attempted = True
    try:
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
        if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
            from supabase import create_client
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            for _bucket in (_PALM_BUCKET, _KUNDLI_BUCKET):
                try:
                    _supabase_client.storage.get_bucket(_bucket)
                except Exception:
                    try:
                        _supabase_client.storage.create_bucket(_bucket, options={"public": False})
                        logger.info("Created Supabase bucket: %s", _bucket)
                    except Exception as e:
                        logger.warning("Could not create bucket %s: %s", _bucket, e)
            logger.info("Supabase Storage connected (buckets: %s, %s)", _PALM_BUCKET, _KUNDLI_BUCKET)
    except Exception as e:
        logger.warning(f"Supabase Storage unavailable: {e}")
    return _supabase_client


def _upload_to_bucket(bucket: str, subfolder: str, file_bytes: bytes, original_filename: str) -> Optional[str]:
    """Shared upload helper — uploads to the given Supabase bucket or local fallback."""
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    supabase = _get_supabase()
    if supabase is not None:
        try:
            path = f"{subfolder}/{filename}"
            supabase.storage.from_(bucket).upload(path, file_bytes, file_options={"content-type": f"image/{ext}"})
            return f"supabase://{bucket}/{path}"
        except Exception as e:
            logger.error("Supabase upload to bucket '%s' failed: %s", bucket, e)
    # Local filesystem fallback (dev / Supabase unavailable)
    try:
        from config import BASE_DIR
        upload_dir = os.path.join(BASE_DIR, "uploads", subfolder)
        os.makedirs(upload_dir, exist_ok=True)
        local_path = os.path.join(upload_dir, filename)
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        return f"uploads/{subfolder}/{filename}"
    except Exception as e:
        logger.error("Local filesystem fallback failed: %s", e)
        return None


def upload_palm_image(file_bytes: bytes, original_filename: str) -> Optional[str]:
    """Upload a palm scan image to the palm-images bucket."""
    return _upload_to_bucket(_PALM_BUCKET, "palm-images", file_bytes, original_filename)


def upload_kundli_image(file_bytes: bytes, original_filename: str) -> Optional[str]:
    """Upload a kundli chart image to the dedicated kundli-images bucket (private)."""
    return _upload_to_bucket(_KUNDLI_BUCKET, "kundli-images", file_bytes, original_filename)


def get_signed_url(storage_path: str, expires_in: int = 3600) -> Optional[str]:
    if not storage_path or not storage_path.startswith("supabase://"):
        return None
    supabase = _get_supabase()
    if supabase is None:
        return None
    try:
        parts = storage_path.replace("supabase://", "").split("/", 1)
        bucket, path = parts[0], parts[1] if len(parts) > 1 else ""
        result = supabase.storage.from_(bucket).create_signed_url(path, expires_in)
        return result.get("signedURL") or result.get("signedUrl")
    except Exception as e:
        logger.error(f"Failed to create signed URL: {e}")
        return None


def delete_file(storage_path: str) -> bool:
    if not storage_path:
        return False
    if storage_path.startswith("supabase://"):
        supabase = _get_supabase()
        if supabase is None:
            return False
        try:
            parts = storage_path.replace("supabase://", "").split("/", 1)
            bucket, path = parts[0], parts[1] if len(parts) > 1 else ""
            supabase.storage.from_(bucket).remove([path])
            return True
        except Exception as e:
            logger.error(f"Failed to delete from Supabase: {e}")
            return False
    else:
        from config import BASE_DIR
        full_path = os.path.join(BASE_DIR, storage_path)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
        except Exception as e:
            logger.error(f"Failed to delete local file: {e}")
        return False
