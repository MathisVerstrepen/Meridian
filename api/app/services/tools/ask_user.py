from typing import Any

from models.tool_question import AskUserAnswerResult, AskUserArguments, AskUserQuestion

ASK_USER_OTHER_VALUE = "__other__"
ASK_USER_OTHER_LABEL = "Other"

ASK_USER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "Ask the user one or more questions, and return their responses."
            "This is useful for gathering additional information from the user that may not be "
            "available in the conversation history. The questions will be shown to the user one "
            "step at a time, and the user's responses will be returned as a JSON object."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Optional short title shown above the paginated questionnaire.",
                },
                "questions": {
                    "type": "array",
                    "description": "One or more questions shown to the user one step at a time.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Optional stable identifier for this question.",
                            },
                            "question": {
                                "type": "string",
                                "description": "The question shown to the user.",
                            },
                            "input_type": {
                                "type": "string",
                                "enum": ["single_select", "multi_select", "boolean", "text"],
                                "description": "The UI control type to render for the user.",
                            },
                            "help_text": {
                                "type": "string",
                                "description": "Optional short guidance shown below the question.",
                            },
                            "options": {
                                "type": "array",
                                "description": (
                                    "Required for single_select and multi_select inputs."
                                ),
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "value": {"type": "string"},
                                        "subtext": {
                                            "type": "string",
                                            "description": (
                                                "Optional compact supporting text "
                                                "shown below the option label."
                                            ),
                                        },
                                    },
                                    "required": ["label", "value"],
                                },
                            },
                            "allow_other": {
                                "type": "boolean",
                                "description": (
                                    "When true, adds an Other option that lets "
                                    "the user type a custom value. Only "
                                    "applicable for single_select and "
                                    "multi_select inputs."
                                ),
                            },
                            "validation": {
                                "type": "object",
                                "description": "Optional UI metadata for text inputs.",
                                "properties": {
                                    "placeholder": {"type": "string"},
                                },
                            },
                        },
                        "required": ["question", "input_type"],
                    },
                },
            },
            "required": ["questions"],
        },
    },
}


async def ask_user(arguments: dict, _req):
    parsed = AskUserArguments.model_validate(arguments)
    return parsed.dump_public()


def normalize_single_ask_user_answer(
    question: AskUserQuestion,
    raw_answer: Any,
) -> dict[str, Any]:
    note = None
    if isinstance(raw_answer, dict) and "note" in raw_answer:
        note = raw_answer.get("note")
        if note is not None and not isinstance(note, str):
            raise ValueError("Note must be a string.")
        if isinstance(note, str):
            note = note.strip() or None

    if question.input_type.value == "boolean":
        answer_value = raw_answer.get("value") if isinstance(raw_answer, dict) else raw_answer
        if not isinstance(answer_value, bool):
            raise ValueError("Answer must be a boolean.")
        answer_payload = {"value": answer_value, "label": "Yes" if answer_value else "No"}
        if note:
            answer_payload["note"] = note
        return answer_payload

    if question.input_type.value == "text":
        answer_value = raw_answer.get("value") if isinstance(raw_answer, dict) else raw_answer
        if not isinstance(answer_value, str):
            raise ValueError("Answer must be a string.")
        if not answer_value.strip():
            raise ValueError("Answer must not be empty.")
        answer_payload = {"value": answer_value}
        if note:
            answer_payload["note"] = note
        return answer_payload

    options = question.options or []
    options_by_value = {option.value: option.label for option in options}

    if question.input_type.value == "single_select":
        selected_value = raw_answer
        other_text = None

        if isinstance(raw_answer, dict):
            selected_value = raw_answer.get("value")
            other_text = raw_answer.get("other_text")

        if not isinstance(selected_value, str):
            raise ValueError("Answer must be a string.")
        if selected_value == ASK_USER_OTHER_VALUE:
            if not question.allow_other:
                raise ValueError("Selected option is invalid.")
            if not isinstance(other_text, str) or not other_text.strip():
                raise ValueError("Other requires a custom value.")
            answer_payload = {
                "value": ASK_USER_OTHER_VALUE,
                "label": ASK_USER_OTHER_LABEL,
                "other_text": other_text.strip(),
            }
            if note:
                answer_payload["note"] = note
            return answer_payload
        if selected_value not in options_by_value:
            raise ValueError("Selected option is invalid.")
        answer_payload = {"value": selected_value, "label": options_by_value[selected_value]}
        if note:
            answer_payload["note"] = note
        return answer_payload

    selected_values = raw_answer
    other_text = None

    if isinstance(raw_answer, dict):
        selected_values = raw_answer.get("values")
        other_text = raw_answer.get("other_text")

    if not isinstance(selected_values, list) or not all(
        isinstance(item, str) for item in selected_values
    ):
        raise ValueError("Answer must be a list of strings.")

    deduped_values: list[str] = []
    other_selected = False
    for value in selected_values:
        if value in deduped_values:
            continue
        if value == ASK_USER_OTHER_VALUE:
            if not question.allow_other:
                raise ValueError("One or more selected options are invalid.")
            other_selected = True
            deduped_values.append(value)
            continue
        if value not in options_by_value:
            raise ValueError("One or more selected options are invalid.")
        deduped_values.append(value)

    if not deduped_values:
        raise ValueError("Select at least one option.")

    if other_selected:
        if not isinstance(other_text, str) or not other_text.strip():
            raise ValueError("Other requires a custom value.")
    elif other_text is not None:
        raise ValueError("Custom other text requires selecting Other.")

    answer_payload = {
        "values": deduped_values,
        "labels": [
            ASK_USER_OTHER_LABEL if value == ASK_USER_OTHER_VALUE else options_by_value[value]
            for value in deduped_values
        ],
    }
    if other_selected:
        answer_payload["other_text"] = str(other_text).strip()
    if note:
        answer_payload["note"] = note

    return answer_payload


def normalize_ask_user_answers(
    arguments: AskUserArguments,
    raw_answer: Any,
) -> list[dict[str, Any]]:
    questions = arguments.questions
    question_ids = {
        question.id or f"question_{index}" for index, question in enumerate(questions, start=1)
    }
    is_question_answer_map = isinstance(raw_answer, dict) and any(
        question_id in raw_answer for question_id in question_ids
    )

    if len(questions) == 1 and not is_question_answer_map:
        question = questions[0]
        return [
            {
                "id": question.id or "question_1",
                "question": question.question,
                "input_type": question.input_type,
                "answer": normalize_single_ask_user_answer(question, raw_answer),
            }
        ]

    if not isinstance(raw_answer, dict):
        raise ValueError("Answer payload must provide one answer for each question.")

    unexpected_ids = [question_id for question_id in raw_answer if question_id not in question_ids]
    if unexpected_ids:
        raise ValueError("Answer payload contains unknown question ids.")

    normalized_answers: list[dict[str, Any]] = []
    for question in questions:
        question_id = question.id or ""
        if question_id not in raw_answer:
            raise ValueError("Answer payload is missing one or more questions.")

        normalized_answers.append(
            {
                "id": question_id,
                "question": question.question,
                "input_type": question.input_type,
                "answer": normalize_single_ask_user_answer(question, raw_answer[question_id]),
            }
        )

    return normalized_answers


def build_ask_user_answer_result(
    arguments: AskUserArguments,
    answer_payloads: list[dict[str, Any]],
    *,
    submitted_at: str,
) -> dict[str, Any]:
    result_kwargs: dict[str, Any] = {
        "title": arguments.title,
        "submitted_at": submitted_at,
        "answers": answer_payloads,
    }

    if len(answer_payloads) == 1:
        first_answer = answer_payloads[0]
        result_kwargs["question"] = first_answer["question"]
        result_kwargs["input_type"] = first_answer["input_type"]
        result_kwargs["answer"] = first_answer["answer"]

    return AskUserAnswerResult(**result_kwargs).model_dump(mode="json", exclude_none=True)
