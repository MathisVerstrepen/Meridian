from typing import Any

from models.tool_question import AskUserArguments

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
                                            "description": "Optional compact supporting text shown below the option label.",
                                        },
                                    },
                                    "required": ["label", "value"],
                                },
                            },
                            "allow_other": {
                                "type": "boolean",
                                "description": (
                                    "When true, adds an Other option that lets the user type a custom value. Only applicable for single_select and multi_select inputs."
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
