# Replay: fixture_wrong_args_repair

Prompt: 写一条笔记，标题是投递总结，内容是已投递 2 个岗位。

## Step 1
- Action: `tool_call` / `write_note`
- Arguments: `{"title": "投递总结"}`
- Status: `failed`
- Observation: `null`
- Error: `wrong_args` Missing required parameter: content
- Verifier feedback: 
- Reward: 0.571

## Step 2
- Action: `self_correction` / `write_note`
- Arguments: `{"title": "投递总结", "content": "已投递 2 个岗位"}`
- Status: `success`
- Observation: `{"note_id": 2, "message": "笔记创建成功"}`
- Error: `` 
- Verifier feedback: content 参数缺失，按 verifier feedback 补齐。
- Reward: 1.000

## Revisions
- Error type: `wrong_args`
- Recovery success: `True`
- Over correction: `False`
- Reward change: `0.571 -> 0.929`

