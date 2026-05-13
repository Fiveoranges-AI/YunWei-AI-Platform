from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from yunwei_win.services import landingai_ade_client as client_module
from yunwei_win.services.landingai_ade_client import parse_large_file_job


class _FakeParseJobs:
    def __init__(self):
        self.polls = 0

    def create(self, *, document, model):
        assert isinstance(document, Path)
        return SimpleNamespace(job_id="job-1")

    def get(self, job_id):
        self.polls += 1
        if self.polls == 1:
            return SimpleNamespace(status="running", progress=0.5)
        return SimpleNamespace(
            status="completed",
            progress=1.0,
            data=SimpleNamespace(markdown="# Done", chunks=[], metadata={}, grounding={}, splits=[]),
        )


class _FakeADE:
    def __init__(self, *, apikey=None, environment="production"):
        self.parse_jobs = _FakeParseJobs()


@pytest.mark.asyncio
async def test_parse_large_file_job_polls_until_completed(monkeypatch, tmp_path):
    monkeypatch.setattr(client_module, "LandingAIADE", _FakeADE)
    monkeypatch.setattr(client_module.settings, "vision_agent_api_key", "test-key")
    path = tmp_path / "large.pdf"
    path.write_bytes(b"%PDF")

    parsed = await parse_large_file_job(path, poll_seconds=0)

    assert parsed.markdown == "# Done"
