import os
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileValidationError

logger = logging.getLogger("clariq.storage")

# Optional Supabase Python Client
_supabase_client = None


def get_supabase_client():
    """Initializes and caches the Supabase Client if secret key is available."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if settings.SUPABASE_URL and settings.SUPABASE_SECRET_KEY:
        try:
            from supabase import create_client

            _supabase_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SECRET_KEY,
            )
            logger.info("Supabase Storage client initialized successfully.")
        except Exception as e:
            logger.warning(
                "Could not initialize Supabase Storage client: %s. Using local fallback.",
                str(e),
            )
            _supabase_client = None

    return _supabase_client


class SupabaseStorageService:
    """
    Manages file attachments in Supabase Storage (bucket: clariq-attachments).
    Features:
    - 10 MB maximum upload size limit
    - File extension and MIME type validation
    - Content validation (PNG, JPG, JPEG, PDF)
    - UUID-based randomized storage filenames
    - Short-lived signed download URLs
    - Automatic fallback for offline / test environments
    """

    def __init__(self, bucket_name: str = settings.SUPABASE_STORAGE_BUCKET):
        self.bucket_name = bucket_name
        self.local_fallback_dir = settings.UPLOAD_DIR
        self.local_fallback_dir.mkdir(parents=True, exist_ok=True)
        # Compatibility attribute
        self.base_dir = self.local_fallback_dir

    def validate_file(
        self,
        file_or_filename: Union[UploadFile, str],
        content_type: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> None:
        """Validates extension, MIME type, and size constraints for UploadFile or raw strings."""
        if isinstance(file_or_filename, UploadFile):
            filename = file_or_filename.filename or ""
            ctype = file_or_filename.content_type or ""
            fsize = getattr(file_or_filename, "size", None)
        else:
            filename = str(file_or_filename)
            ctype = content_type or ""
            fsize = file_size

        if not filename:
            raise FileValidationError("Uploaded file must have a filename.")

        ext = Path(filename).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise FileValidationError(
                f"File extension '{ext}' is not permitted. Allowed: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}"
            )

        if ctype not in settings.ALLOWED_MIME_TYPES:
            raise FileValidationError(
                f"File MIME type '{ctype}' is not allowed. Permitted: PNG, JPEG, PDF."
            )

        if fsize is not None and fsize > settings.MAX_UPLOAD_SIZE:
            max_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
            raise FileValidationError(f"File size exceeds maximum allowed limit of {max_mb} MB.")

    def upload_file_bytes(
        self,
        file_bytes: bytes,
        original_filename: str,
        content_type: str,
        subfolder: str = "doubts",
    ) -> Dict[str, Any]:
        """
        Uploads file bytes to Supabase Storage (or local fallback if Supabase is offline/testing).
        Returns metadata dict for database persistence.
        """
        self.validate_file(original_filename, content_type, len(file_bytes))

        ext = Path(original_filename).suffix.lower()
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        storage_key = f"{subfolder}/{stored_filename}".lstrip("/")

        client = get_supabase_client()
        uploaded_to_supabase = False

        if client is not None:
            try:
                # Ensure bucket exists
                try:
                    client.storage.get_bucket(self.bucket_name)
                except Exception:
                    client.storage.create_bucket(self.bucket_name, options={"public": False})

                client.storage.from_(self.bucket_name).upload(
                    path=storage_key,
                    file=file_bytes,
                    file_options={"content-type": content_type, "upsert": "false"},
                )
                uploaded_to_supabase = True
                logger.info("Uploaded attachment '%s' to Supabase Storage: %s", original_filename, storage_key)
            except Exception as e:
                logger.error("Supabase Storage upload failed: %s. Storing in local fallback.", str(e))

        # Always save to local fallback/cache for fast retrieval and test compatibility
        fallback = self.base_dir if self.base_dir is not None else self.local_fallback_dir
        target_path = fallback / subfolder / stored_filename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(file_bytes)

        if not uploaded_to_supabase:
            storage_key = str(target_path)

        return {
            "original_filename": Path(original_filename).name,
            "stored_filename": stored_filename,
            "mime_type": content_type,
            "file_size": len(file_bytes),
            "storage_path": storage_key,
            "is_cloud_storage": uploaded_to_supabase,
        }

    def save_file(self, file: UploadFile, subfolder: str = "doubts") -> Dict[str, Any]:
        """Backward compatible helper taking an UploadFile directly."""
        content = file.file.read()
        return self.upload_file_bytes(
            file_bytes=content,
            original_filename=file.filename,
            content_type=file.content_type,
            subfolder=subfolder,
        )

    def get_file_path(self, stored_filename: str, subfolder: str = "doubts") -> Path:
        """Backward compatible helper resolving local path."""
        safe_name = Path(stored_filename).name
        fallback = self.base_dir if self.base_dir is not None else self.local_fallback_dir
        target = (fallback / subfolder / safe_name).resolve()
        return target

    def get_signed_url(self, storage_path: str, expires_in_seconds: int = 60) -> Optional[str]:
        """Generates a short-lived signed download URL for private attachments."""
        client = get_supabase_client()
        if client is not None and not os.path.isabs(storage_path):
            try:
                res = client.storage.from_(self.bucket_name).create_signed_url(
                    storage_path, expires_in_seconds
                )
                return res.get("signedURL") or res.get("signedUrl")
            except Exception as e:
                logger.error("Failed to generate signed URL for '%s': %s", storage_path, str(e))
        return None

    def download_file_bytes(self, storage_path: str) -> bytes:
        """Retrieves raw file bytes from Supabase Storage or local fallback."""
        client = get_supabase_client()
        if client is not None and not os.path.isabs(storage_path):
            try:
                return client.storage.from_(self.bucket_name).download(storage_path)
            except Exception as e:
                logger.error("Supabase Storage download failed for '%s': %s", storage_path, str(e))

        # Fallback to local filesystem
        path = Path(storage_path)
        if not path.is_absolute():
            fallback = self.base_dir if self.base_dir is not None else self.local_fallback_dir
            path = fallback / storage_path
        if path.exists():
            return path.read_bytes()

        raise FileValidationError(f"Attachment file not found at path '{storage_path}'.")

    def delete_file(self, storage_path: str) -> bool:
        """Cleans up an attachment file upon cancellation or error."""
        client = get_supabase_client()
        if client is not None and not os.path.isabs(storage_path):
            try:
                client.storage.from_(self.bucket_name).remove([storage_path])
                return True
            except Exception:
                pass

        path = Path(storage_path)
        if path.exists():
            path.unlink(missing_ok=True)
            return True
        return False


storage_service = SupabaseStorageService()
