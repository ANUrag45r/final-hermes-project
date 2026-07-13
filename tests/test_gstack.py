"""Tests for the gstack skills integration."""
import os
import stat
import tempfile

import pytest

from app.core.config import Settings
from app.services.hermes.control_service import (
    HermesControlError,
    HermesControlService,
)
from app.services.hermes.gstack_service import CURATED_SKILLS, GStackService


def _fake_hermes(body: str) -> str:
    import sys
    py_content = f"""#!/usr/bin/env python3
import sys
import re

body = {repr(body)}

if "make-pdf" in body and "productivity" in body:
    print("| Name | Category | Source | Trust | Status |")
    print("| make-pdf | productivity | builtin | builtin | enabled |")
    print("| powerpoint | productivity | builtin | builtin | enabled |")
elif "Saved file" in body:
    m = re.search(r'Saved file to ([^\\s"\\']+)', body)
    path = m.group(1) if m else ""
    print(f"Saved file to {{path}}")
elif "Fake review output" in body:
    prompt = sys.argv[3] if len(sys.argv) > 3 else ""
    print(f"Fake review output for {{prompt}}")
else:
    print("ok")
"""
    fd, py_path = tempfile.mkstemp(suffix=".py")
    os.write(fd, py_content.encode('utf-8'))
    os.close(fd)
    
    if os.name == 'nt':
        bat_content = f'@"{sys.executable}" "{py_path}" %*\n'
        fd_bat, bat_path = tempfile.mkstemp(suffix=".bat")
        os.write(fd_bat, bat_content.encode('utf-8'))
        os.close(fd_bat)
        return bat_path
    else:
        os.chmod(py_path, os.stat(py_path).st_mode | stat.S_IEXEC)
        return py_path


@pytest.fixture(autouse=True)
def _mock_hermes_control():
    from app.main import app
    from app.core.dependencies import get_hermes_control_service
    # Provide a simple mock hermes executable that returns a basic list table
    body = "echo '| Name | Category | Source | Trust | Status |';" \
           "echo '| make-pdf | productivity | builtin | builtin | enabled |'"
    fake_exe = _fake_hermes(body)
    fake_svc = HermesControlService(Settings(hermes_cli_path=fake_exe))
    app.dependency_overrides[get_hermes_control_service] = lambda: fake_svc
    yield
    app.dependency_overrides.clear()


def _svc(body: str, reports_dir: str) -> GStackService:
    settings = Settings(hermes_cli_path=_fake_hermes(body), reports_dir=reports_dir)
    return GStackService(settings, HermesControlService(settings))


def test_curated_has_mandatory_pdf():
    pdf = [s for s in CURATED_SKILLS if s["id"] == "make-pdf"]
    assert pdf and pdf[0]["mandatory"] is True
    assert 3 <= len(CURATED_SKILLS) <= 4


def test_list_installed_parses_table(tmp_path):
    table = (
        "echo '| Name | Category | Source | Trust | Status |';"
        "echo '| make-pdf | productivity | builtin | builtin | enabled |';"
        "echo '| powerpoint | productivity | builtin | builtin | enabled |'"
    )
    svc = _svc("#!/usr/bin/env bash\n" + table + "\n", str(tmp_path))
    skills = svc.list_installed()
    names = {s["name"] for s in skills}
    assert "make-pdf" in names and "powerpoint" in names
    assert "Name" not in names  # header filtered


def test_run_skill_invokes_and_detects_file(tmp_path):
    # Fake hermes echoes a saved path so produced_file is detected.
    body = "#!/usr/bin/env bash\necho \"Saved file to %s/make-pdf-M1.pdf\"\n" % tmp_path
    svc = _svc(body, str(tmp_path))
    res = svc.run_skill("make-pdf", "M1", "Demo", "owners and actions here")
    assert res["ok"] is True
    assert res["skill"] == "make-pdf"
    assert res["produced_file"] and res["produced_file"].endswith("make-pdf-M1.pdf")


def test_run_skill_rejects_unknown(tmp_path):
    svc = _svc("#!/usr/bin/env bash\necho ok\n", str(tmp_path))
    with pytest.raises(HermesControlError):
        svc.run_skill("not-a-skill", "M1", "t", "content")


def test_skills_route(client):
    r = client.get("/agent/skills")
    assert r.status_code == 200
    body = r.json()
    assert any(s["id"] == "make-pdf" for s in body["curated"])


def test_run_skill_route_404(client):
    r = client.post("/agent/skills/run", json={"skill_id": "make-pdf", "meeting_id": "NOPE"})
    assert r.status_code == 404


def test_load_skill_instructions_success(tmp_path):
    gstack_dir = tmp_path / "gstack"
    gstack_dir.mkdir()
    skill_dir = gstack_dir / "plan-ceo-review"
    skill_dir.mkdir()

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: plan-ceo-review\n"
        "description: CEO Review\n"
        "---\n"
        "## Preamble (run first)\n"
        "echo hello\n"
        "## Main Instructions\n"
        "Here are CEO guidelines.",
        encoding="utf-8"
    )

    sections_dir = skill_dir / "sections"
    sections_dir.mkdir()
    sections_md = sections_dir / "review-sections.md"
    sections_md.write_text(
        "## Review Items\n"
        "Look for resources.",
        encoding="utf-8"
    )

    # Instantiate service
    settings = Settings(gstack_dir=str(gstack_dir), hermes_cli_path="hermes")
    svc = GStackService(settings, HermesControlService(settings))

    instructions = svc.load_skill_instructions("plan-ceo-review")
    assert "## Main Instructions" in instructions
    assert "Here are CEO guidelines." in instructions
    assert "## Review Items" in instructions
    assert "Look for resources." in instructions
    assert "Preamble" not in instructions
    assert "echo hello" not in instructions
    assert "name: plan-ceo-review" not in instructions


def test_load_skill_instructions_missing(tmp_path):
    settings = Settings(gstack_dir=str(tmp_path), hermes_cli_path="hermes")
    svc = GStackService(settings, HermesControlService(settings))
    instructions = svc.load_skill_instructions("non-existent-skill")
    assert instructions == ""


def test_run_autoplan(tmp_path):
    body = "#!/usr/bin/env bash\necho \"Fake review output for $3\"\n"
    svc = _svc(body, str(tmp_path))
    res = svc.run_autoplan("M1", "Demo Meeting", "This is meeting content")
    assert res["ok"] is True
    assert "ceo" in res["reviews"]
    assert "design" in res["reviews"]
    assert "eng" in res["reviews"]
    assert "devex" in res["reviews"]
    assert "Fake review output" in res["output"]


def test_run_skill_on_transcript(tmp_path):
    body = "#!/usr/bin/env bash\necho \"Fake review output for $3\"\n"
    svc = _svc(body, str(tmp_path))
    res = svc.run_skill_on_transcript("spec", "This is meeting transcript content")
    assert res["ok"] is True
    assert res["skill"] == "spec"
    assert "Fake review" in res["output"]


