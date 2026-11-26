import io
import pytest
from pathlib import Path
from app.core.config import settings
from app.services.storage import storage_service, get_supabase_client
from app.core.exceptions import FileValidationError


def test_psycopg_driver_resolution():
    """Verify database URL normalizes to postgresql+psycopg driver."""
    test_pg = "postgresql://postgres:pass@db.supabase.co:5432/postgres"
    old_env = settings.DATABASE_URL_ENV
    try:
        settings.DATABASE_URL_ENV = test_pg
        assert settings.database_url.startswith("postgresql+psycopg://")
    finally:
        settings.DATABASE_URL_ENV = old_env


def test_supabase_config_and_bucket():
    assert "xkxpptzhirajzjntkrlb.supabase.co" in settings.SUPABASE_URL
    assert settings.SUPABASE_PUBLISHABLE_KEY.startswith("sb_publishable_")
    assert settings.SUPABASE_STORAGE_BUCKET == "clariq-attachments"


def test_storage_validation_pdf_png_jpg():
    """Verify allowed MIME types and extensions."""
    storage_service.validate_file("document.pdf", "application/pdf", 1024)
    storage_service.validate_file("diagram.png", "image/png", 2048)
    storage_service.validate_file("photo.jpg", "image/jpeg", 4096)
    storage_service.validate_file("notes.jpeg", "image/jpeg", 8192)


def test_storage_reject_invalid_mime():
    with pytest.raises(FileValidationError) as exc:
        storage_service.validate_file("malicious.sh", "application/x-sh", 100)
    assert "File extension '.sh' is not permitted" in str(exc.value)

    with pytest.raises(FileValidationError) as exc:
        storage_service.validate_file("doc.pdf", "text/plain", 100)
    assert "File MIME type 'text/plain' is not allowed" in str(exc.value)


def test_storage_reject_oversized_file():
    eleven_mb = 11 * 1024 * 1024
    with pytest.raises(FileValidationError) as exc:
        storage_service.validate_file("large.pdf", "application/pdf", eleven_mb)
    assert "exceeds maximum allowed limit" in str(exc.value)


def test_storage_upload_and_download_flow(tmp_path):
    """Test full upload, byte download, and cleanup flow."""
    storage_service.local_fallback_dir = tmp_path
    content = b"%PDF-1.4 Mock PDF content for ClariQ test"
    meta = storage_service.upload_file_bytes(
        file_bytes=content,
        original_filename="sample_assignment.pdf",
        content_type="application/pdf",
        subfolder="test_doubts",
    )

    assert meta["original_filename"] == "sample_assignment.pdf"
    assert meta["mime_type"] == "application/pdf"
    assert meta["file_size"] == len(content)
    assert meta["stored_filename"].endswith(".pdf")

    downloaded = storage_service.download_file_bytes(meta["storage_path"])
    assert downloaded == content

    # Cleanup
    deleted = storage_service.delete_file(meta["storage_path"])
    assert deleted is True
