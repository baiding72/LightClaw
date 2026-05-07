"""Conservative HTML extractors for safe recruiting dry-runs.

The extractors are fixture-friendly and deliberately non-invasive. They parse
static HTML snapshots and never submit forms, upload files, log in, or bypass
site controls.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    job_id: str | None = None
    title: str
    company: str | None = None
    location: str | None = None
    job_url: str | None = None
    source: str = "html_fixture"


class JobDetail(BaseModel):
    job_id: str | None = None
    title: str
    company: str | None = None
    location: str | None = None
    description: str = ""
    requirements: list[str] = Field(default_factory=list)
    apply_url: str | None = None
    page_title: str | None = None


class ApplyStep(BaseModel):
    step_id: str
    label: str
    control_type: str
    required: bool = False
    safe_to_autofill: bool = False
    requires_user: bool = True


class _RecruitingHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.jobs: list[dict[str, Any]] = []
        self.apply_steps: list[dict[str, Any]] = []
        self.detail: dict[str, Any] = {"requirements": []}
        self.title_parts: list[str] = []
        self._stack: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        node = {"tag": tag, "attrs": attr, "text": [], "children": []}
        self._stack.append(node)

        if tag == "input":
            self._capture_apply_control(tag, attr)
        elif tag in {"textarea", "select", "button"}:
            self._capture_apply_control(tag, attr)

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        node = self._stack.pop()
        text = _normalize_text(" ".join(node["text"]))
        attrs = node["attrs"]

        if tag == "title" and text:
            self.title_parts.append(text)

        role = attrs.get("data-role") or attrs.get("data-agent-role")
        if role == "job-card":
            self.jobs.append({
                "job_id": attrs.get("data-job-id") or attrs.get("id") or None,
                "title": attrs.get("data-title") or _first_text(node, "data-field", "title") or text,
                "company": attrs.get("data-company") or _first_text(node, "data-field", "company"),
                "location": attrs.get("data-location") or _first_text(node, "data-field", "location"),
                "job_url": attrs.get("data-url") or _first_link(node),
            })
        elif role == "job-detail":
            self.detail.update({
                "job_id": attrs.get("data-job-id") or None,
                "title": attrs.get("data-title") or _first_text(node, "data-field", "title") or text,
                "company": attrs.get("data-company") or _first_text(node, "data-field", "company"),
                "location": attrs.get("data-location") or _first_text(node, "data-field", "location"),
                "description": _first_text(node, "data-field", "description") or text,
                "apply_url": attrs.get("data-apply-url") or _first_link(node),
            })
            requirements = _all_text(node, "data-field", "requirement")
            if requirements:
                self.detail["requirements"] = requirements

        if self._stack:
            self._stack[-1]["text"].append(text)
            self._stack[-1]["children"].append(node)

    def handle_data(self, data: str) -> None:
        if self._stack:
            self._stack[-1]["text"].append(data)

    def _capture_apply_control(self, tag: str, attrs: dict[str, str]) -> None:
        if tag == "input" and attrs.get("type", "").lower() in {"hidden", "submit", "button"}:
            return
        label = attrs.get("data-label") or attrs.get("aria-label") or attrs.get("placeholder") or attrs.get("name")
        if not label:
            return
        control_type = attrs.get("type") or tag
        self.apply_steps.append({
            "step_id": attrs.get("data-step-id") or attrs.get("id") or attrs.get("name") or f"step_{len(self.apply_steps) + 1}",
            "label": label,
            "control_type": control_type,
            "required": "required" in attrs or attrs.get("aria-required") == "true",
            "safe_to_autofill": attrs.get("data-safe-autofill") == "true",
            "requires_user": attrs.get("data-requires-user", "true") != "false",
        })


def extract_job_list(html: str) -> list[JobPosting]:
    parser = _parse(html)
    return [
        JobPosting(
            job_id=job.get("job_id"),
            title=job.get("title") or "Untitled job",
            company=job.get("company"),
            location=job.get("location"),
            job_url=job.get("job_url"),
        )
        for job in parser.jobs
        if job.get("title")
    ]


def extract_job_detail(html: str) -> JobDetail:
    parser = _parse(html)
    detail = parser.detail
    return JobDetail(
        job_id=detail.get("job_id"),
        title=detail.get("title") or "Untitled job",
        company=detail.get("company"),
        location=detail.get("location"),
        description=detail.get("description") or "",
        requirements=detail.get("requirements") or [],
        apply_url=detail.get("apply_url"),
        page_title=parser.title_parts[0] if parser.title_parts else None,
    )


def extract_apply_flow(html: str) -> list[ApplyStep]:
    parser = _parse(html)
    return [ApplyStep.model_validate(step) for step in parser.apply_steps]


def truncate_dom_snapshot(html: str, limit: int = 4000) -> str:
    text = _normalize_text(html)
    return text[:limit]


def _parse(html: str) -> _RecruitingHTMLParser:
    parser = _RecruitingHTMLParser()
    parser.feed(html)
    parser.close()
    return parser


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _first_text(node: dict[str, Any], attr_name: str, attr_value: str) -> str | None:
    values = _all_text(node, attr_name, attr_value)
    return values[0] if values else None


def _all_text(node: dict[str, Any], attr_name: str, attr_value: str) -> list[str]:
    values: list[str] = []
    attrs = node.get("attrs", {})
    if attrs.get(attr_name) == attr_value:
        text = _normalize_text(" ".join(node.get("text", [])))
        if text:
            values.append(text)
    for child in node.get("children", []):
        values.extend(_all_text(child, attr_name, attr_value))
    return values


def _first_link(node: dict[str, Any]) -> str | None:
    attrs = node.get("attrs", {})
    if attrs.get("href") or attrs.get("data-url") or attrs.get("data-apply-url"):
        return attrs.get("href") or attrs.get("data-url") or attrs.get("data-apply-url")
    for child in node.get("children", []):
        link = _first_link(child)
        if link:
            return link
    return None
