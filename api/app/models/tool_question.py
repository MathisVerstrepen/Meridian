from enum import Enum
from typing import Any

from pydantic import BaseModel, model_validator


class AskUserInputType(str, Enum):
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    BOOLEAN = "boolean"
    TEXT = "text"


class AskUserOption(BaseModel):
    label: str
    value: str
    subtext: str | None = None


class AskUserValidation(BaseModel):
    placeholder: str | None = None


class AskUserQuestion(BaseModel):
    id: str | None = None
    question: str
    input_type: AskUserInputType
    help_text: str | None = None
    options: list[AskUserOption] | None = None
    allow_other: bool = False
    validation: AskUserValidation | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "AskUserQuestion":
        if self.input_type in {AskUserInputType.SINGLE_SELECT, AskUserInputType.MULTI_SELECT}:
            if not self.options:
                raise ValueError("options are required for select inputs.")
        elif self.options is not None:
            raise ValueError("options are only allowed for select inputs.")

        if (
            self.input_type
            not in {
                AskUserInputType.SINGLE_SELECT,
                AskUserInputType.MULTI_SELECT,
            }
            and self.allow_other
        ):
            raise ValueError("allow_other is only allowed for select inputs.")

        if self.input_type != AskUserInputType.TEXT and self.validation is not None:
            raise ValueError("validation is only allowed for text inputs.")

        return self


class AskUserArguments(BaseModel):
    title: str | None = None
    questions: list[AskUserQuestion]

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        if data.get("questions") is not None:
            return data

        if data.get("question") is None or data.get("input_type") is None:
            return data

        normalized_question = {
            key: value
            for key, value in {
                "id": data.get("id"),
                "question": data.get("question"),
                "input_type": data.get("input_type"),
                "help_text": data.get("help_text"),
                "options": data.get("options"),
                "allow_other": data.get("allow_other"),
                "validation": data.get("validation"),
            }.items()
            if value is not None
        }

        normalized_data: dict[str, Any] = {"questions": [normalized_question]}
        if data.get("title") is not None:
            normalized_data["title"] = data.get("title")
        return normalized_data

    @model_validator(mode="after")
    def validate_questions(self) -> "AskUserArguments":
        if not self.questions:
            raise ValueError("questions must contain at least one question.")

        seen_ids: set[str] = set()
        for index, question in enumerate(self.questions, start=1):
            normalized_id = (question.id or "").strip() or f"question_{index}"
            if normalized_id in seen_ids:
                raise ValueError("question ids must be unique.")
            question.id = normalized_id
            seen_ids.add(normalized_id)

        return self

    def dump_public(self) -> dict[str, Any]:
        return self.model_dump(include={"title", "questions"}, exclude_none=True)


AskUserAnswerValue = str | list[str] | bool


class AskUserContinuationAnswer(BaseModel):
    tool_call_id: str
    answer: Any


class AskUserPendingResult(BaseModel):
    status: str = "pending_user_input"


class AskUserAnswerItem(BaseModel):
    id: str
    question: str
    input_type: AskUserInputType
    answer: dict[str, Any]


class AskUserAnswerResult(BaseModel):
    title: str | None = None
    submitted_at: str
    answers: list[AskUserAnswerItem]
    question: str | None = None
    input_type: AskUserInputType | None = None
    answer: dict[str, Any] | None = None
