"""
Supabase Storage service for Celestial Arc.
Handles palm image uploads/deletions via Supabase Storage.
Falls back to local filesystem if Supabase is not configured.
"""
import logging
import os
import uuid
from typing import Optional

logger = logging.getLogger(__name__)
_supabase_client = None
_supabase_init_attempted = False
_BUCKET_NAME = "palm-images"


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
            try:
                _supabase_client.storage.get_bucket(_BUCKET_NAME)
            except Exception:
                try:
                    _supabase_client.storage.create_bucket(_BUCKET_NAME, options={"public": False})
                except Exception as e:
                    logger.warning(f"Could not create bucket: {e}")
            logger.info("Supabase Storage connected")
    except Exception as e:
        logger.warning(f"Supabase Storage unavailable: {e}")
    return _supabase_client


def upload_palm_image(file_bytes: bytes, original_filename: str) -> Optional[str]:
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    supabase = _get_supabase()
    if supabase is not None:
        try:
            path = f"palm-images/{filename}"
            supabase.storage.from_(_BUCKET_NAME).upload(path, file_bytes, file_options={"content-type": f"image/{ext}"})
            return f"supabase://{_BUCKET_NAME}/{path}"
        except Exception as e:
            logger.error(f"Supabase upload failed: {e}")
    from config import BASE_DIR
    upload_dir = os.path.join(BASE_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    local_path = os.path.join(upload_dir, filename)
    with open(local_path, "wb") as f:
        f.write(file_bytes)
    return f"uploads/{filename}"


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
