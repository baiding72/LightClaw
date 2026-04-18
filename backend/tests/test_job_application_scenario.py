from app.scenarios.job_application import build_job_application_instruction


def test_build_job_application_instruction_includes_profile_and_checkpoints() -> None:
    instruction = build_job_application_instruction(
        "搜索值得投递的公司并整理结果。",
        {
            "target_company": "OpenAI",
            "target_role": "Software Engineer Intern",
            "search_preferences": {
                "role_keywords": ["software engineer intern", "systems"],
                "target_companies": ["OpenAI", "Anthropic"],
                "internship_only": True,
            },
            "candidate_profile": {
                "full_name": "Ada Lovelace",
                "email": "ada@example.com",
                "resume_path": "/tmp/ada_resume.pdf",
            },
            "require_user_confirmation_for_login": True,
            "require_user_confirmation_for_submit": True,
        },
    )

    assert "目标公司: OpenAI" in instruction
    assert "目标岗位: Software Engineer Intern" in instruction
    assert "候选人资料:" in instruction
    assert "登录" in instruction
    assert "提交申请" in instruction
