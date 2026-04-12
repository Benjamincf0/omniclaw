from __future__ import annotations

from omniclaw_orchestrator.tool_hints import (
    augment_tool_description,
    build_orchestration_system_prompt,
)


def test_augment_tool_description_adds_dependency_hint() -> None:
    description = augment_tool_description(
        "get_lea_assignments",
        "Fetch the assignments page for a LEA class.",
    )

    assert "Requires a class section URL returned by get_lea_classes" in description
    assert "all my assignments" in description


def test_build_orchestration_system_prompt_uses_exact_tool_names() -> None:
    prompt = build_orchestration_system_prompt(
        ["omnivox__get_lea_classes", "omnivox__get_lea_assignments"]
    )

    assert "Infer and execute prerequisite tool calls yourself" in prompt
    assert "omnivox__get_lea_classes" in prompt
    assert "omnivox__get_lea_assignments" in prompt
    assert "do not stop after listing classes" in prompt
