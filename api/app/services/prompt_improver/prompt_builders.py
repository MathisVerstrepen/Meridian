import json
from typing import Any

from const.prompts import (
    PROMPT_IMPROVER_ANALYZER_SYSTEM_PROMPT_TEMPLATE,
    PROMPT_IMPROVER_CLARIFICATION_SYSTEM_PROMPT_TEMPLATE,
    PROMPT_IMPROVER_EXPLAINER_SYSTEM_PROMPT_TEMPLATE,
    PROMPT_IMPROVER_GENERATOR_SYSTEM_PROMPT,
    PROMPT_IMPROVER_ISSUE_DETECTOR_SYSTEM_PROMPT,
)
from database.pg.models import ToolCallStatusEnum
from models.prompt_improver import PromptImproverAudit, PromptImproverClarificationRound

from .context import compact_target_profile
from .review import DiffCluster
from .schemas import IssueDetectorResponseSchema
from .taxonomy import TAXONOMY_DEFINITIONS, taxonomy_json


def build_analyzer_user_prompt(
    *,
    source_prompt: str,
    target_snapshot: dict[str, Any],
    sibling_context_text: str,
    template_snapshot: dict[str, Any] | None,
    clarification_context_text: str,
) -> str:
    return (
        "<prompt_to_audit>\n"
        f"{source_prompt}\n"
        "</prompt_to_audit>\n\n"
        "<target_profile>\n"
        f"{json.dumps(compact_target_profile(target_snapshot), indent=2)}\n"
        "</target_profile>\n\n"
        "<sibling_context>\n"
        f"{sibling_context_text}\n"
        "</sibling_context>\n\n"
        "<clarification_context>\n"
        f"{clarification_context_text}\n"
        "</clarification_context>\n\n"
        "<template_context>\n"
        f"{json.dumps(template_snapshot, indent=2) if template_snapshot else 'null'}\n"
        "</template_context>"
    )


def build_issue_detector_user_prompt(
    *,
    source_prompt: str,
    target_snapshot: dict[str, Any],
    sibling_context_text: str,
    clarification_context_text: str,
) -> str:
    return (
        "<prompt_to_audit>\n"
        f"{source_prompt}\n"
        "</prompt_to_audit>\n\n"
        "<target_profile>\n"
        f"{json.dumps(compact_target_profile(target_snapshot), indent=2)}\n"
        "</target_profile>\n\n"
        "<sibling_context>\n"
        f"{sibling_context_text}\n"
        "</sibling_context>\n\n"
        "<clarification_context>\n"
        f"{clarification_context_text}\n"
        "</clarification_context>"
    )


def build_generator_user_prompt(
    *,
    source_prompt: str,
    selected_dimensions: list[str],
    audit: PromptImproverAudit,
    target_snapshot: dict[str, Any],
    sibling_context_text: str,
    issue_detector: IssueDetectorResponseSchema,
    feedback: str | None,
    clarification_context_text: str,
) -> str:
    dimension_details = [
        {
            "id": dimension.id,
            "label": dimension.label,
            "description": dimension.description,
            "tier": dimension.tier,
        }
        for dimension in TAXONOMY_DEFINITIONS
        if dimension.id in selected_dimensions
    ]
    return (
        "<current_prompt>\n"
        f"{source_prompt}\n"
        "</current_prompt>\n\n"
        "<selected_dimensions>\n"
        f"{json.dumps(dimension_details, indent=2)}\n"
        "</selected_dimensions>\n\n"
        "<audit>\n"
        f"{audit.model_dump_json(indent=2)}\n"
        "</audit>\n\n"
        "<issue_detector>\n"
        f"{issue_detector.model_dump_json(indent=2)}\n"
        "</issue_detector>\n\n"
        "<target_profile>\n"
        f"{json.dumps(compact_target_profile(target_snapshot), indent=2)}\n"
        "</target_profile>\n\n"
        "<sibling_context>\n"
        f"{sibling_context_text}\n"
        "</sibling_context>\n\n"
        "<clarification_context>\n"
        f"{clarification_context_text}\n"
        "</clarification_context>\n\n"
        "<feedback>\n"
        f"{feedback or 'null'}\n"
        "</feedback>"
    )


def build_explainer_user_prompt(
    *,
    source_prompt: str,
    improved_prompt: str,
    changes: list[DiffCluster],
    selected_dimensions: list[str],
) -> str:
    return (
        "<original_prompt>\n"
        f"{source_prompt}\n"
        "</original_prompt>\n\n"
        "<improved_prompt>\n"
        f"{improved_prompt}\n"
        "</improved_prompt>\n\n"
        "<selected_dimensions>\n"
        f"{json.dumps(selected_dimensions, indent=2)}\n"
        "</selected_dimensions>\n\n"
        "<diff_clusters>\n"
        f"{json.dumps(changes, indent=2)}\n"
        "</diff_clusters>"
    )


def analyzer_system_prompt() -> str:
    return PROMPT_IMPROVER_ANALYZER_SYSTEM_PROMPT_TEMPLATE.format(taxonomy_json=taxonomy_json())


def issue_detector_system_prompt() -> str:
    return PROMPT_IMPROVER_ISSUE_DETECTOR_SYSTEM_PROMPT


def generator_system_prompt() -> str:
    return PROMPT_IMPROVER_GENERATOR_SYSTEM_PROMPT


def clarification_system_prompt(phase: str) -> str:
    return PROMPT_IMPROVER_CLARIFICATION_SYSTEM_PROMPT_TEMPLATE.format(phase=phase)


def explainer_system_prompt() -> str:
    return PROMPT_IMPROVER_EXPLAINER_SYSTEM_PROMPT_TEMPLATE.format(taxonomy_json=taxonomy_json())


def format_clarification_context(rounds: list[PromptImproverClarificationRound]) -> str:
    answered_rounds = [
        round_ for round_ in rounds if round_.status == ToolCallStatusEnum.SUCCESS.value
    ]
    if not answered_rounds:
        return "No prior clarification answers."

    sections: list[str] = []
    for index, round_ in enumerate(answered_rounds, start=1):
        result = round_.result if isinstance(round_.result, dict) else {}
        answers = result.get("answers") if isinstance(result, dict) else []
        if not isinstance(answers, list):
            continue

        lines = [f"Round {index}:"]
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            question = str(answer.get("question") or "").strip()
            answer_payload = answer.get("answer")
            answer_summary = ""
            if isinstance(answer_payload, dict):
                if isinstance(answer_payload.get("label"), str):
                    answer_summary = str(answer_payload["label"])
                elif isinstance(answer_payload.get("labels"), list):
                    answer_summary = ", ".join(
                        str(label) for label in answer_payload["labels"] if isinstance(label, str)
                    )
                elif isinstance(answer_payload.get("value"), bool):
                    answer_summary = "Yes" if answer_payload["value"] else "No"
                elif isinstance(answer_payload.get("value"), str):
                    answer_summary = str(answer_payload["value"])
                elif isinstance(answer_payload.get("values"), list):
                    answer_summary = ", ".join(
                        str(value) for value in answer_payload["values"] if isinstance(value, str)
                    )
                if (
                    isinstance(answer_payload.get("other_text"), str)
                    and answer_payload["other_text"].strip()
                ):
                    if answer_summary:
                        answer_summary = (
                            f"{answer_summary} ({answer_payload['other_text'].strip()})"
                        )
                    else:
                        answer_summary = str(answer_payload["other_text"]).strip()
                if isinstance(answer_payload.get("note"), str) and answer_payload["note"].strip():
                    answer_summary = (
                        f"{answer_summary} | Note: {answer_payload['note'].strip()}"
                        if answer_summary
                        else f"Note: {answer_payload['note'].strip()}"
                    )
            if question and answer_summary:
                lines.append(f"- {question}: {answer_summary}")
        if len(lines) > 1:
            sections.append("\n".join(lines))

    return "\n\n".join(sections) if sections else "No prior clarification answers."


def build_draft_clarification_prompt(
    *,
    source_prompt: str,
    target_snapshot: dict[str, Any],
    sibling_context_text: str,
    template_snapshot: dict[str, Any] | None,
    clarification_context_text: str,
) -> str:
    return (
        "<phase_goal>\n"
        "Decide whether the prompt improver needs clarifying questions before running the prompt "
        "audit.\n"
        "</phase_goal>\n\n"
        "<prompt_to_audit>\n"
        f"{source_prompt}\n"
        "</prompt_to_audit>\n\n"
        "<target_profile>\n"
        f"{json.dumps(compact_target_profile(target_snapshot), indent=2)}\n"
        "</target_profile>\n\n"
        "<sibling_context>\n"
        f"{sibling_context_text}\n"
        "</sibling_context>\n\n"
        "<clarification_context>\n"
        f"{clarification_context_text}\n"
        "</clarification_context>\n\n"
        "<template_context>\n"
        f"{json.dumps(template_snapshot, indent=2) if template_snapshot else 'null'}\n"
        "</template_context>"
    )


def build_improve_clarification_prompt(
    *,
    source_prompt: str,
    selected_dimensions: list[str],
    target_snapshot: dict[str, Any],
    sibling_context_text: str,
    audit: PromptImproverAudit | None,
    feedback: str | None,
    clarification_context_text: str,
) -> str:
    return (
        "<phase_goal>\n"
        "Decide whether the prompt improver needs clarifying questions before generating an "
        "improved prompt.\n"
        "</phase_goal>\n\n"
        "<current_prompt>\n"
        f"{source_prompt}\n"
        "</current_prompt>\n\n"
        "<selected_dimensions>\n"
        f"{json.dumps(selected_dimensions, indent=2)}\n"
        "</selected_dimensions>\n\n"
        "<audit>\n"
        f"{audit.model_dump_json(indent=2) if audit else 'null'}\n"
        "</audit>\n\n"
        "<feedback>\n"
        f"{feedback or 'null'}\n"
        "</feedback>\n\n"
        "<target_profile>\n"
        f"{json.dumps(compact_target_profile(target_snapshot), indent=2)}\n"
        "</target_profile>\n\n"
        "<sibling_context>\n"
        f"{sibling_context_text}\n"
        "</sibling_context>\n\n"
        "<clarification_context>\n"
        f"{clarification_context_text}\n"
        "</clarification_context>"
    )
