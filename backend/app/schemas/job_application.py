"""
求职投递场景相关 Schema
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    """候选人资料"""

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    current_school: Optional[str] = None
    graduation_year: Optional[str] = None
    degree: Optional[str] = None
    major: Optional[str] = None
    work_authorization: Optional[str] = None
    resume_path: Optional[str] = None
    highlights: list[str] = Field(default_factory=list)


class JobSearchPreferences(BaseModel):
    """岗位搜索偏好"""

    role_keywords: list[str] = Field(default_factory=list)
    target_companies: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    internship_only: bool = True
    preferred_sources: list[str] = Field(default_factory=list)


class JobSiteProfile(BaseModel):
    """招聘站点配置"""

    site_key: str
    display_name: str
    domains: list[str] = Field(default_factory=list)
    login_url_keywords: list[str] = Field(default_factory=list)
    login_title_keywords: list[str] = Field(default_factory=list)
    login_content_keywords: list[str] = Field(default_factory=list)
    authenticated_content_keywords: list[str] = Field(default_factory=list)
    application_record_url_keywords: list[str] = Field(default_factory=list)
    application_record_content_keywords: list[str] = Field(default_factory=list)


class JobApplicationContext(BaseModel):
    """求职投递任务上下文"""

    search_preferences: Optional[JobSearchPreferences] = None
    candidate_profile: Optional[CandidateProfile] = None
    target_company: Optional[str] = None
    target_role: Optional[str] = None
    source_url: Optional[str] = None
    application_notes: Optional[str] = None
    require_user_confirmation_for_login: bool = True
    require_user_confirmation_for_submit: bool = True
    extra_context: dict[str, Any] = Field(default_factory=dict)


class ApplicationCreate(BaseModel):
    """创建申请记录"""

    company_name: str = Field(..., min_length=1, max_length=200)
    role_title: str = Field(..., min_length=1, max_length=200)
    status: str = "discovered"
    source_url: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    next_action: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApplicationUpdate(BaseModel):
    """更新申请记录"""

    status: Optional[str] = None
    source_url: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    next_action: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ApplicationResponse(BaseModel):
    """申请记录响应"""

    application_id: str
    company_name: str
    role_title: str
    status: str
    source_url: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    next_action: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationListResponse(BaseModel):
    """申请记录列表响应"""

    applications: list[ApplicationResponse]
    total: int
