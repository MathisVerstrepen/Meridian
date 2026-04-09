from difflib import SequenceMatcher
from typing import TypedDict

from database.pg.models import PromptImproverChange, PromptImproverChangeStatusEnum
from database.pg.prompt_improver_ops import PromptImproverChangePayload

from .schemas import ChangeExplanationResponseSchema
from .taxonomy import coerce_impact, taxonomy_index


class DiffCluster(TypedDict):
    order_index: int
    source_start: int
    source_end: int
    source_text: str
    suggested_text: str


def build_diff_clusters(source_prompt: str, improved_prompt: str) -> list[DiffCluster]:
    matcher = SequenceMatcher(a=source_prompt, b=improved_prompt)
    pending_cluster: dict[str, int] | None = None
    raw_clusters: list[dict[str, int]] = []

    for tag, source_start, source_end, target_start, target_end in matcher.get_opcodes():
        if tag == "equal":
            if not pending_cluster:
                continue

            if (source_end - source_start) <= 24 and (target_end - target_start) <= 24:
                pending_cluster["source_end"] = source_end
                pending_cluster["target_end"] = target_end
                continue

            raw_clusters.append(pending_cluster)
            pending_cluster = None
            continue

        if not pending_cluster:
            pending_cluster = {
                "source_start": source_start,
                "source_end": source_end,
                "target_start": target_start,
                "target_end": target_end,
            }
            continue

        pending_cluster["source_end"] = source_end
        pending_cluster["target_end"] = target_end

    if pending_cluster:
        raw_clusters.append(pending_cluster)

    return [
        {
            "order_index": index,
            "source_start": cluster["source_start"],
            "source_end": cluster["source_end"],
            "source_text": source_prompt[cluster["source_start"] : cluster["source_end"]],
            "suggested_text": improved_prompt[cluster["target_start"] : cluster["target_end"]],
        }
        for index, cluster in enumerate(raw_clusters)
    ]


def compose_prompt(source_prompt: str, changes: list[PromptImproverChange]) -> str:
    if not changes:
        return source_prompt

    cursor = 0
    parts: list[str] = []
    for change in sorted(changes, key=lambda item: item.order_index):
        parts.append(source_prompt[cursor : change.source_start])
        if change.review_status == PromptImproverChangeStatusEnum.REJECTED:
            parts.append(change.source_text)
        else:
            parts.append(change.suggested_text)
        cursor = change.source_end
    parts.append(source_prompt[cursor:])
    return "".join(parts)


def normalize_explanations(
    explanations: ChangeExplanationResponseSchema,
    changes: list[DiffCluster],
    selected_dimensions: list[str],
) -> list[PromptImproverChangePayload]:
    normalized: list[PromptImproverChangePayload] = []
    known_dimensions = taxonomy_index()
    for index, change in enumerate(changes):
        explanation = (
            explanations.explanations[index] if index < len(explanations.explanations) else None
        )
        dimension_id = explanation.dimension_id if explanation else None
        if dimension_id not in known_dimensions:
            dimension_id = selected_dimensions[0] if selected_dimensions else "clarity_specificity"
        normalized.append(
            {
                "order_index": int(change["order_index"]),
                "source_start": int(change["source_start"]),
                "source_end": int(change["source_end"]),
                "source_text": str(change["source_text"]),
                "suggested_text": str(change["suggested_text"]),
                "title": explanation.title if explanation else "Prompt improvement",
                "dimension_id": dimension_id,
                "rationale": explanation.rationale if explanation else "Improves prompt quality.",
                "impact": (
                    explanation.impact
                    if explanation and explanation.impact in {"High", "Medium", "Low"}
                    else coerce_impact(dimension_id)
                ),
                "review_status": PromptImproverChangeStatusEnum.ACCEPTED.value,
            }
        )
    return normalized
