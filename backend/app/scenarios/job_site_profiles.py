"""
招聘站点 profile 与页面状态检测
"""
from __future__ import annotations

from urllib.parse import urlparse

from app.schemas.job_application import JobSiteProfile


JOB_SITE_PROFILES: list[JobSiteProfile] = [
    JobSiteProfile(
        site_key="meituan",
        display_name="美团招聘",
        domains=["zhaopin.meituan.com", "hr.meituan.com", "campus.meituan.com", "job.meituan.com"],
        login_url_keywords=["/login", "signin", "auth", "passport"],
        login_title_keywords=["登录", "美团招聘"],
        login_content_keywords=["手机登录", "扫码登录", "获取验证码", "个人信息保护隐私政策"],
        authenticated_content_keywords=["个人中心", "投递记录", "我的申请", "退出登录"],
        application_record_url_keywords=["delivery-record", "application", "personal-center"],
        application_record_content_keywords=["投递记录", "已投递", "申请记录", "岗位状态"],
    ),
    JobSiteProfile(
        site_key="ant_group",
        display_name="蚂蚁集团招聘",
        domains=["talent.antgroup.com"],
        login_url_keywords=["login", "sso", "auth"],
        login_title_keywords=["登录", "统一登录中心"],
        login_content_keywords=["登录", "验证码", "扫码", "统一登录中心"],
        authenticated_content_keywords=["个人中心", "我的申请", "投递记录", "退出"],
        application_record_url_keywords=["personal", "application", "record"],
        application_record_content_keywords=["我的申请", "投递记录", "申请状态"],
    ),
    JobSiteProfile(
        site_key="alibaba",
        display_name="阿里巴巴招聘",
        domains=["campus.alibaba.com", "talent.alibaba.com", "mozi-login.alibaba-inc.com"],
        login_url_keywords=["login", "sso", "signin", "auth"],
        login_title_keywords=["登录", "统一登录中心"],
        login_content_keywords=["登录", "验证码", "统一登录中心", "扫码"],
        authenticated_content_keywords=["我的申请", "申请记录", "个人中心", "退出"],
        application_record_url_keywords=["applications", "record", "personal"],
        application_record_content_keywords=["我的申请", "申请记录", "职位状态"],
    ),
]


def detect_job_site_profile(url: str | None) -> JobSiteProfile | None:
    if not url:
        return None
    hostname = (urlparse(url).hostname or "").lower()
    for profile in JOB_SITE_PROFILES:
        if any(hostname == domain or hostname.endswith(f".{domain}") for domain in profile.domains):
            return profile
    return None


def detect_login_state(
    profile: JobSiteProfile | None,
    *,
    url: str | None,
    title: str | None,
    content: str | None,
) -> bool:
    if not profile:
        return False
    url_lower = (url or "").lower()
    title_text = title or ""
    content_text = content or ""

    if any(keyword.lower() in url_lower for keyword in profile.login_url_keywords):
        return True
    if any(keyword in title_text for keyword in profile.login_title_keywords) and any(
        keyword in content_text for keyword in profile.login_content_keywords
    ):
        return True
    return any(keyword in content_text for keyword in profile.login_content_keywords)


def detect_application_record_page(
    profile: JobSiteProfile | None,
    *,
    url: str | None,
    content: str | None,
) -> bool:
    if not profile:
        return False
    url_lower = (url or "").lower()
    content_text = content or ""
    url_match = any(keyword.lower() in url_lower for keyword in profile.application_record_url_keywords)
    content_match = any(keyword in content_text for keyword in profile.application_record_content_keywords)
    return url_match or content_match

