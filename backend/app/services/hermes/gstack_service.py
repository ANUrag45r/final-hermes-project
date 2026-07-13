"""
GStack skills integration.

gstack skills are agent capabilities Hermes can invoke (the `hermes skills list`
catalogue). We expose:
  * a curated set of skills relevant to meetings (PDF is mandatory), each
    runnable against a meeting from the UI, and
  * the full installed-skills catalogue (parsed from `hermes skills list`) so
    the user can see everything available.

A skill is invoked by instructing Hermes (agentic, --yolo) to use it on the
meeting's content. For artifact-producing skills (make-pdf, powerpoint) we ask
Hermes to save the file into the reports folder and report its path.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.core.config import Settings
from app.services.hermes.control_service import (
    HermesControlError,
    HermesControlService,
)
from app.utils.logger import get_logger

logger = get_logger("gstack")

# Curated, meeting-relevant skills surfaced as one-click actions in the UI.
# `produces_file` skills are asked to save an artifact to the reports folder.
CURATED_SKILLS = [
    {
        "id": "make-pdf",
        "label": "Generate PDF report",
        "category": "productivity",
        "produces_file": True,
        "ext": "pdf",
        "description": "Render a polished management-report PDF from the meeting.",
        "mandatory": True,
    },
    {
        "id": "powerpoint",
        "label": "Build slide deck",
        "category": "productivity",
        "produces_file": True,
        "ext": "pptx",
        "description": "Create a PowerPoint summarising the meeting.",
        "mandatory": False,
    },
    {
        "id": "document-generate",
        "label": "Generate document",
        "category": "creative",
        "produces_file": True,
        "ext": "md",
        "description": "Produce a structured written document from the meeting.",
        "mandatory": False,
    },
    {
        "id": "ocr-and-documents",
        "label": "Summarise & extract",
        "category": "productivity",
        "produces_file": False,
        "ext": None,
        "description": "Extract key facts, owners and actions from the transcript.",
        "mandatory": False,
    },
]

_CURATED_BY_ID = {s["id"]: s for s in CURATED_SKILLS}
_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+|/[^\s\"']+")


class GStackService:
    def __init__(self, settings: Settings, control: HermesControlService) -> None:
        self.settings = settings
        self.control = control

    # ----- catalogue -----
    @property
    def curated(self) -> list[dict]:
        return CURATED_SKILLS

    def list_installed(self, timeout: float = 30.0) -> list[dict]:
        """Parse `hermes skills list` into [{name, category, status}]."""
        exe = self.control._resolve_exe()
        try:
            proc = subprocess.run(
                [exe, "skills", "list"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise HermesControlError(
                f"Hermes executable not found at '{exe}'. Set HERMES_CLI_PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HermesControlError("`hermes skills list` timed out.") from exc

        skills: list[dict] = []
        for line in (proc.stdout or "").splitlines():
            if "│" not in line and "|" not in line:
                continue
            parts = [p.strip() for p in re.split(r"[│|]", line)]
            parts = [p for p in parts if p != ""]
            if len(parts) < 2:
                continue
            name = parts[0]
            if not name or name.lower() == "name" or set(name) <= set("─━ "):
                continue
            category = parts[1] if len(parts) > 1 else ""
            status = parts[-1]
            skills.append({"name": name, "category": category, "status": status})
        return skills

    def load_skill_instructions(self, skill_name: str) -> str:
        if not self.settings.gstack_dir:
            return ""
        gstack_path = Path(self.settings.gstack_dir)
        skill_path = gstack_path / skill_name
        if not skill_path.is_dir():
            return ""

        # Find SKILL.md or SKILL.md.tmpl
        skill_file = skill_path / "SKILL.md"
        if not skill_file.exists():
            skill_file = skill_path / "SKILL.md.tmpl"

        # Find sections/review-sections.md or sections/review-sections.md.tmpl
        sections_file = skill_path / "sections" / "review-sections.md"
        if not sections_file.exists():
            sections_file = skill_path / "sections" / "review-sections.md.tmpl"

        parts = []
        for path in [skill_file, sections_file]:
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    content = self._clean_skill_content(content)
                    if content:
                        parts.append(content)
                except Exception as exc:
                    logger.warning("Failed to read GStack skill file %s: %s", path, exc)

        return "\n\n".join(parts)

    def _clean_skill_content(self, content: str) -> str:
        # Strip YAML frontmatter
        content = content.strip()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()

        # Strip preamble under ## Preamble
        lines = content.splitlines()
        cleaned_lines = []
        in_preamble = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## Preamble"):
                in_preamble = True
                continue
            if in_preamble and stripped.startswith("#"):
                in_preamble = False
            if not in_preamble:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    # ----- invocation -----
    def run_skill(
        self,
        skill_id: str,
        meeting_id: str,
        title: str,
        content: str,
        timeout: float = 300.0,
    ) -> dict:
        spec = _CURATED_BY_ID.get(skill_id)
        if spec is None:
            raise HermesControlError(f"Unknown skill '{skill_id}'.")

        content = (content or "").strip()
        if not content:
            raise HermesControlError("Nothing to run the skill on (empty content).")
        content = content[:12000]

        save_dir = None
        file_clause = ""
        if spec["produces_file"]:
            save_dir = Path(
                self.settings.reports_dir or (Path.home() / "governance-reports")
            )
            save_dir.mkdir(parents=True, exist_ok=True)
            fname = f"{skill_id}-{meeting_id}.{spec['ext']}"
            target = save_dir / fname
            file_clause = (
                f" Save the resulting file to '{target}' and reply with the full "
                f"saved file path on its own line."
            )

        instructions = self.load_skill_instructions(skill_id)
        if instructions:
            prompt = (
                f"Use the '{skill_id}' skill to {spec['description'].lower()} "
                f"This is for meeting {meeting_id} titled '{title}'.{file_clause}\n\n"
                f"Skill Instructions:\n{instructions}\n\n"
                f"MEETING CONTENT:\n{content}"
            )
        else:
            prompt = (
                f"Use the '{skill_id}' skill to {spec['description'].lower()} "
                f"This is for meeting {meeting_id} titled '{title}'.{file_clause}\n\n"
                f"MEETING CONTENT:\n{content}"
            )

        res = self.control._exec(
            ["chat", "-q", prompt, "--yolo"],
            action=f"skill:{skill_id}",
            timeout=timeout,
        )
        res["skill"] = skill_id
        res["command"] = f"hermes chat -q (skill {skill_id} for {meeting_id})"

        # Best-effort: detect a saved file path in the output and confirm it exists.
        produced = None
        if spec["produces_file"]:
            for m in _PATH_RE.findall(res.get("output", "")):
                if m.lower().endswith(f".{spec['ext']}"):
                    produced = m
                    break
        res["produced_file"] = produced
        return res

    def run_skill_on_transcript(
        self,
        skill_name: str,
        transcript: str,
        timeout: float = 300.0,
    ) -> dict:
        """Run a specific gstack skill (e.g. 'spec' or 'retro') directly on raw transcript."""
        transcript = (transcript or "").strip()
        if not transcript:
            raise HermesControlError("Nothing to run the skill on (empty transcript).")
        transcript = transcript[:12000]

        instructions = self.load_skill_instructions(skill_name)
        if instructions:
            prompt = (
                f"Use the '{skill_name}' skill instructions to analyze the meeting transcript below.\n\n"
                f"Skill Instructions:\n{instructions}\n\n"
                f"MEETING TRANSCRIPT:\n{transcript}"
            )
        else:
            if skill_name == "spec":
                fallback = (
                    "Generate a detailed technical specification based on the following meeting content, "
                    "outlining architecture, requirements, endpoints, database schema changes, and implementation steps."
                )
            elif skill_name == "retro":
                fallback = (
                    "Generate a sprint retrospective report based on the following meeting content, "
                    "highlighting achievements, risks/blockers, action items, and owners."
                )
            else:
                fallback = f"Evaluate this meeting transcript using the '{skill_name}' skill."
            prompt = f"{fallback}\n\nMEETING TRANSCRIPT:\n{transcript}"

        res = self.control._exec(
            ["chat", "-q", prompt, "--yolo"],
            action=f"skill:{skill_name}",
            timeout=timeout,
        )
        res["skill"] = skill_name
        res["command"] = f"hermes chat -q (skill {skill_name} on transcript)"
        return res

    def run_autoplan(
        self,
        meeting_id: str,
        title: str,
        content: str,
        timeout: float = 300.0,
    ) -> dict:
        # Define the reviews to run
        reviews_config = [
            {
                "key": "ceo",
                "skill": "plan-ceo-review",
                "label": "CEO Review",
                "fallback_prompt": "Evaluate this meeting from a Chief Executive Officer (CEO) perspective. Look for high-level business alignment, resource constraints, and overall strategic goals."
            },
            {
                "key": "design",
                "skill": "plan-design-review",
                "label": "Design Review",
                "fallback_prompt": "Evaluate this meeting from a Product Design perspective. Analyze user experience, user interface, design consistency, and product flow."
            },
            {
                "key": "eng",
                "skill": "plan-eng-review",
                "label": "Engineering Review",
                "fallback_prompt": "Evaluate this meeting from an Engineering perspective. Examine architecture, implementation complexity, performance, scalability, and code quality."
            },
            {
                "key": "devex",
                "skill": "plan-devex-review",
                "label": "Developer Experience (DX) Review",
                "fallback_prompt": "Evaluate this meeting from a Developer Experience (DX) perspective. Assess developer onboarding, documentation, development speed, and developer tooling."
            }
        ]

        reviews_output = {}
        ok = True
        combined_output_parts = []

        for rev in reviews_config:
            instructions = self.load_skill_instructions(rev["skill"])
            prompt_intro = f"Perform a {rev['label']} on the following meeting content.\n"
            if instructions:
                prompt_intro += f"Use the following detailed review guidelines:\n{instructions}\n\n"
            else:
                prompt_intro += f"Guideline: {rev['fallback_prompt']}\n\n"

            prompt = f"{prompt_intro}MEETING TITLE: {title}\nMEETING CONTENT:\n{content}"

            try:
                res = self.control._exec(
                    ["chat", "-q", prompt, "--yolo"],
                    action=f"autoplan:{rev['key']}",
                    timeout=timeout,
                )
                output = res.get("output", "").strip()
                reviews_output[rev["key"]] = output
                combined_output_parts.append(f"### {rev['label']}\n\n{output}")
                if not res.get("ok", False):
                    ok = False
            except Exception as exc:
                logger.error("Failed to run autoplan review %s: %s", rev["key"], exc)
                reviews_output[rev["key"]] = f"Review failed: {exc}"
                combined_output_parts.append(f"### {rev['label']}\n\nReview failed: {exc}")
                ok = False

        return {
            "ok": ok,
            "output": "\n\n".join(combined_output_parts),
            "reviews": reviews_output,
        }
