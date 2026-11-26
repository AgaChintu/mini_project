import pytest
import io
from pathlib import Path
from fastapi import UploadFile
from app.services.storage import storage_service
from app.core.exceptions import FileValidationError
from app.core.config import settings


def test_cors_configuration():
    assert len(settings.cors_origins) >= 1
    assert any("5500" in o for o in settings.cors_origins)


def test_env_in_gitignore():
    gitignore_path = Path(__file__).resolve().parents[2] / ".gitignore"
    assert gitignore_path.exists(), "Root .gitignore must exist"
    content = gitignore_path.read_text()
    assert ".env" in content, ".gitignore must ignore .env files"


def test_storage_validation_disallowed_extension():
    fake_file = UploadFile(
        filename="malicious.exe",
        file=io.BytesIO(b"fake binary content"),
        headers={"content-type": "application/x-msdownload"},
    )
    with pytest.raises(FileValidationError):
        storage_service.validate_file(fake_file)


def test_storage_validation_disallowed_mime():
    fake_file = UploadFile(
        filename="document.txt",
        file=io.BytesIO(b"plain text"),
        headers={"content-type": "text/plain"},
    )
    with pytest.raises(FileValidationError):
        storage_service.validate_file(fake_file)


def test_storage_save_and_retrieve(tmp_path):
    storage_service.base_dir = tmp_path
    content = b"fake pdf data content"
    test_file = UploadFile(
        filename="notes.pdf",
        file=io.BytesIO(content),
        headers={"content-type": "application/pdf"},
    )
    res = storage_service.save_file(test_file, subfolder="test_doubts")
    assert res["original_filename"] == "notes.pdf"
    assert res["mime_type"] == "application/pdf"
    assert res["file_size"] == len(content)

    resolved_path = storage_service.get_file_path(res["stored_filename"], subfolder="test_doubts")
    assert resolved_path.exists()
    assert resolved_path.read_bytes() == content
