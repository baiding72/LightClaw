"""Safety guardrails for recruiting trajectory collection."""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.schemas.action import StopReason


@dataclass(frozen=True)
class RecruitingGuardResult:
    allowed: bool
    stop_reason: StopReason | None = None
    message: str = ""


class RecruitingGuard:
    """Blocks unsafe recruiting actions.

    This guard intentionally errs on the side of stopping. It does not solve
    login, CAPTCHA, upload, or application submission flows.
    """

    def validate_action(self, action_name: str, html: str = "") -> RecruitingGuardResult:
        normalized = action_name.lower()
        if "submit" in normalized or "apply_submit" in normalized:
            return RecruitingGuardResult(
                allowed=False,
                stop_reason=StopReason.SAFE_STOP,
                message="Blocked unsafe submit action in recruiting dry-run.",
            )
        page_check = self.inspect_page(html)
        if not page_check.allowed:
            return page_check
        return RecruitingGuardResult(allowed=True)

    def inspect_page(self, html: str) -> RecruitingGuardResult:
        lower_html = html.lower()
        if _looks_like_login_required(lower_html):
            return RecruitingGuardResult(
                allowed=False,
                stop_reason=StopReason.LOGIN_REQUIRED,
                message="Detected login-required recruiting page; stopping before account flow.",
            )
        if _looks_like_captcha(lower_html):
            return RecruitingGuardResult(
                allowed=False,
                stop_reason=StopReason.CAPTCHA_BLOCKED,
                message="Detected CAPTCHA or anti-bot challenge; stopping safely.",
            )
        if "type=\"file\"" in lower_html or "type='file'" in lower_html:
            if os.getenv("ALLOW_REAL_UPLOAD", "").lower() != "true":
                return RecruitingGuardResult(
                    allowed=False,
                    stop_reason=StopReason.SAFE_STOP,
                    message="Detected file upload field; set ALLOW_REAL_UPLOAD=true only for explicit local tests.",
                )
        return RecruitingGuardResult(allowed=True)


def _looks_like_login_required(lower_html: str) -> bool:
    markers = [
        "data-requires-login=\"true\"",
        "data-login-required=\"true\"",
        "请登录",
        "登录后",
        "sign in",
        "login required",
    ]
    return any(marker in lower_html for marker in markers)


def _looks_like_captcha(lower_html: str) -> bool:
    markers = ["captcha", "验证码", "人机验证", "verify you are human"]
    return any(marker in lower_html for marker in markers)
