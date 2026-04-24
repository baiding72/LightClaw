from app.gui_grounding import (
    CandidateBox,
    GroundingInput,
    GroundingLabel,
    RuleBasedGroundingModule,
    bbox_iou,
    gui_action_accuracy,
    point_in_box,
)


def test_point_in_box_metric() -> None:
    assert point_in_box((15, 15), (10, 10, 20, 20)) is True
    assert point_in_box((25, 15), (10, 10, 20, 20)) is False


def test_bbox_iou_metric() -> None:
    assert bbox_iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert bbox_iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0


def test_rule_based_grounding_selects_matching_button() -> None:
    module = RuleBasedGroundingModule()
    prediction = module.predict(
        GroundingInput(
            instruction="请点击保存按钮",
            candidates=[
                CandidateBox(candidate_id="cancel", selector="#cancel", text="取消", role="button", bbox=(0, 0, 50, 30)),
                CandidateBox(candidate_id="save", selector="#save", text="保存", role="button", bbox=(60, 0, 110, 30)),
            ],
        )
    )
    label = GroundingLabel(candidate_id="save", selector="#save", bbox=(60, 0, 110, 30))

    assert prediction.selector == "#save"
    assert gui_action_accuracy([prediction], [label]) == 1.0
