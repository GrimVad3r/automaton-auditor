"""
Tests for CLI input resolution helpers in src.main.
"""

from pathlib import Path

import pytest
import typer

import src.main as main_module
from src.utils.exceptions import AutomatonAuditorException


class _FakeHTTPResponse:
    """Minimal context-managed HTTP response for tests."""

    def __init__(self, payload: bytes, headers: dict[str, str] | None = None):
        self._payload = payload
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestSourceMode:
    """Tests for explicit source-mode selection flags."""

    def test_resolve_source_mode_local(self):
        assert main_module._resolve_source_mode(local_pdf=True, remote_pdf=False) == "local"

    def test_resolve_source_mode_remote(self):
        assert main_module._resolve_source_mode(local_pdf=False, remote_pdf=True) == "remote"

    def test_resolve_source_mode_both_flags_error(self):
        with pytest.raises(typer.BadParameter):
            main_module._resolve_source_mode(local_pdf=True, remote_pdf=True)


class TestPDFInputResolution:
    """Tests for local/remote PDF input normalization."""

    def test_resolve_local_filename_recursively(self, temp_dir, monkeypatch):
        nested = temp_dir / "docs"
        nested.mkdir()
        pdf_file = nested / "Week2_Interim_Report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%%EOF\n")
        monkeypatch.chdir(temp_dir)

        resolved = main_module._resolve_pdf_input(
            "Week2_Interim_Report.pdf",
            output_dir=temp_dir,
            source_mode="local",
        )

        assert resolved == pdf_file.resolve()

    def test_remote_mode_rejects_non_url(self, temp_dir):
        with pytest.raises(AutomatonAuditorException):
            main_module._resolve_pdf_input(
                "Week2_Interim_Report.pdf",
                output_dir=temp_dir,
                source_mode="remote",
            )

    def test_local_mode_rejects_url(self, temp_dir):
        with pytest.raises(AutomatonAuditorException):
            main_module._resolve_pdf_input(
                "https://example.com/report.pdf",
                output_dir=temp_dir,
                source_mode="local",
            )

    def test_google_drive_url_is_downloaded(self, temp_dir, monkeypatch):
        payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"

        def fake_urlopen(request, timeout=30):
            return _FakeHTTPResponse(payload, {"Content-Type": "application/pdf"})

        monkeypatch.setattr(main_module, "urlopen", fake_urlopen)

        resolved = main_module._resolve_pdf_input(
            "https://drive.google.com/file/d/abc123/view?usp=sharing",
            output_dir=temp_dir,
            source_mode="remote",
        )

        assert resolved.exists()
        assert resolved.suffix.lower() == ".pdf"
        assert resolved.read_bytes() == payload

    def test_remote_download_rejects_non_pdf_payload(self, temp_dir, monkeypatch):
        def fake_urlopen(request, timeout=30):
            return _FakeHTTPResponse(
                b"<html>not a pdf</html>",
                {"Content-Type": "text/html"},
            )

        monkeypatch.setattr(main_module, "urlopen", fake_urlopen)

        with pytest.raises(AutomatonAuditorException):
            main_module._resolve_pdf_input(
                "https://example.com/report.pdf",
                output_dir=temp_dir,
                source_mode="remote",
            )
