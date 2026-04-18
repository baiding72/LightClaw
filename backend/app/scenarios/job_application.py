"""
求职投递场景指令组装
"""
from typing import Any

from app.schemas.job_application import JobApplicationContext


def _format_list(title: str, values: list[str]) -> list[str]:
    if not values:
        return []
    return [f"{title}:"] + [f"- {value}" for value in values]


def build_job_application_instruction(
    base_instruction: str,
    scenario_context: dict[str, Any] | None,
) -> str:
    """把求职场景上下文展开为运行时指令块"""

    if not scenario_context:
        return base_instruction

    context = JobApplicationContext(**scenario_context)
    lines = [
        "当前任务属于求职投递闭环场景，请围绕岗位发现、官网查询、内容整理、投递准备与后续跟进执行。",
    ]

    if context.target_company:
        lines.append(f"目标公司: {context.target_company}")
    if context.target_role:
        lines.append(f"目标岗位: {context.target_role}")
    if context.source_url:
        lines.append(f"已知申请入口: {context.source_url}")
    if context.application_notes:
        lines.append(f"投递备注: {context.application_notes}")

    if context.search_preferences:
        prefs = context.search_preferences
        lines.extend(_format_list("岗位关键词", prefs.role_keywords))
        lines.extend(_format_list("目标公司列表", prefs.target_companies))
        lines.extend(_format_list("工作地点偏好", prefs.locations))
        if prefs.preferred_sources:
            lines.extend(_format_list("优先检索来源", prefs.preferred_sources))
        lines.append(f"是否仅关注实习: {'是' if prefs.internship_only else '否'}")

    if context.candidate_profile:
        profile = context.candidate_profile
        lines.append("候选人资料:")
        if profile.full_name:
            lines.append(f"- 姓名: {profile.full_name}")
        if profile.email:
            lines.append(f"- 邮箱: {profile.email}")
        if profile.phone:
            lines.append(f"- 电话: {profile.phone}")
        if profile.current_school:
            lines.append(f"- 学校: {profile.current_school}")
        if profile.degree or profile.major or profile.graduation_year:
            lines.append(
                "- 教育信息: "
                + " / ".join(
                    item for item in [profile.degree, profile.major, profile.graduation_year] if item
                )
            )
        if profile.work_authorization:
            lines.append(f"- 工作授权: {profile.work_authorization}")
        if profile.resume_path:
            lines.append(f"- 简历文件: {profile.resume_path}")
        if profile.highlights:
            lines.extend(_format_list("个人亮点", profile.highlights))

    if context.extra_context:
        lines.append("补充上下文:")
        for key, value in context.extra_context.items():
            lines.append(f"- {key}: {value}")

    checkpoint_lines = ["高风险动作要求:"]
    if context.require_user_confirmation_for_login:
        checkpoint_lines.append("- 遇到官网登录、验证码、双因素验证时暂停并请求用户确认。")
    if context.require_user_confirmation_for_submit:
        checkpoint_lines.append("- 在最终提交申请、发送邮件或外发资料前暂停并请求用户确认。")
    checkpoint_lines.append("- 如果页面字段与候选人资料无法一一对齐，先输出缺失字段，再继续填写。")

    return f"{base_instruction}\n\n" + "\n".join(lines + checkpoint_lines)
