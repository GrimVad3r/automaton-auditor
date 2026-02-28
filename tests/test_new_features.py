import json
from pathlib import Path

import pytest

from src.agents.detectives.vision_inspector import VisionInspector
from src.core.config import get_config
from src.main import _store_peer_report
from src.utils.formatters import MarkdownReportFormatter


def test_vision_inspector_no_images(monkeypatch, tmp_path):
    inspector = VisionInspector()
    monkeypatch.setattr(inspector, "_extract_images", lambda p: [])
    state = {"pdf_path": str(tmp_path / "dummy.pdf")}
    result = inspector.investigate(state)
    evidence = result["evidences"]["VisionInspector"][0]
    assert evidence.found is False
    assert "No extractable images" in (evidence.content or "")


def test_vision_inspector_counts_without_llm(monkeypatch, tmp_path):
    inspector = VisionInspector()
    inspector.config.openai_api_key = None
    monkeypatch.setattr(inspector, "_extract_images", lambda p: [b"fakeimagebytes"])
    summary = inspector._summarize_images([b"fakeimagebytes"])
    assert "LLM unavailable" in summary


def test_store_peer_report_manifest(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    pdf = tmp_path / "peer.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%EOF")
    saved = _store_peer_report(str(pdf), source_mode="local", label="peer1")
    manifest = Path("audit") / "report_bypeer_received" / "manifest.jsonl"
    assert saved.exists()
    assert manifest.exists()
    lines = manifest.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["label"] == "peer1"
    assert entry["saved_as"] == saved.name


def test_format_triage_report():
    report = MarkdownReportFormatter.format_triage_report(
        repo_url="https://example.com/repo",
        pdf_path="report.pdf",
        final_scores={"c1": 3},
        synthesis_summary="summary",
        remediation="fix things",
        execution_time=1.23,
    )
    assert "Automaton Auditor Triage Report" in report
    assert "| c1 | 3/5 |" in report


def test_vision_model_config(monkeypatch):
    cfg = get_config(require_llm_keys=False)
    monkeypatch.setattr(cfg, "default_vision_model", "test-vision-model")
    monkeypatch.setattr(cfg, "openai_api_key", "dummy-key")
    inspector = VisionInspector()
    inspector.config = cfg  # inject modified config

    captured = {}

    class DummyLLM:
        def __init__(self, model, temperature, max_tokens):
            captured["model"] = model

        def invoke(self, messages):
            return type("DummyResp", (), {"content": "ok"})

    monkeypatch.setattr("src.agents.detectives.vision_inspector.ChatOpenAI", DummyLLM)
    summary = inspector._summarize_images([b"img"])
    assert "Detected 1 image" in summary
    assert captured["model"] == "test-vision-model"
