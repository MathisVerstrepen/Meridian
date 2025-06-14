from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
import pybase64 as base64
import asyncio
from typing import Coroutine, Any
from pathlib import Path

from database.pg.models import Node, Files

from models.message import (
    Message,
    MessageRoleEnum,
    MessageContent,
    MessageContentTypeEnum,
    MessageContentFile,
    MessageContentImageURL,
    MessageTypeEnum,
    IMG_EXT_TO_MIME_TYPE,
)

from database.pg.crud import (
    get_file_by_id,
)


def system_message_builder(
    system_prompt: str,
) -> Message | None:
    """
    Builds a system message object from the provided system prompt.

    Args:
        system_prompt (str): The system prompt text to include in the message.

    Returns:
        Message: A Message object with the system role and the given prompt as content,
            or None if no system_prompt is provided.
    """
    return (
        Message(
            role=MessageRoleEnum.system,
            content=[
                MessageContent(
                    type=MessageContentTypeEnum.text,
                    text=system_prompt,
                )
            ],
        )
        if system_prompt
        else None
    )


def _encode_file_as_data_uri(file_path: Path, mime_type: str) -> str:
    """Reads a file and encodes it into a base64 data URI."""
    with open(file_path, "rb") as f:
        encoded_data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded_data}"


async def _create_message_content_from_file(
    pg_engine: SQLAlchemyAsyncEngine, file_info: dict, add_file_content: bool
) -> MessageContent | None:
    """
    Fetches a file and creates a corresponding MessageContent object.
    Returns None if the file type is unsupported.
    """
    file_record: Files = await get_file_by_id(
        pg_engine=pg_engine, file_id=file_info.get("id")
    )
    if not file_record:
        return None

    file_type = file_info.get("type")
    file_path = Path(file_record.file_path)

    if not add_file_content:
        file_data = file_path.name
    else:
        # Prepare mime_type for data URI encoding
        if file_type == "pdf":
            mime_type = "application/pdf"
        elif file_type == "image":
            mime_type = IMG_EXT_TO_MIME_TYPE.get(
                file_path.suffix.lstrip("."), "image/png"
            )
        else:
            mime_type = "application/octet-stream"

        file_data = _encode_file_as_data_uri(file_path, mime_type)

    # Construct the appropriate MessageContent type
    if file_type == "pdf":
        return MessageContent(
            type=MessageContentTypeEnum.file,
            file=MessageContentFile(filename=file_record.filename, file_data=file_data),
        )
    elif file_type == "image":
        return MessageContent(
            type=MessageContentTypeEnum.image_url,
            image_url=MessageContentImageURL(url=file_data),
        )

    return None


async def prompt_message_builder(
    pg_engine: SQLAlchemyAsyncEngine,
    node: Node,
    previousNode: Node | None = None,
    add_file_content: bool = True,
) -> Message:
    """
    Builds a message object from a prompt node, attaching file content
    from the previous node if it's a FILE_PROMPT.

    Args:
        pg_engine: The SQLAlchemy async engine.
        node: The current node containing the prompt text.
        previousNode: The preceding node, checked for file data.
        add_file_content: If True, file content is base64 encoded.
                          If False, only the filename is used.

    Returns:
        A Message object with the user role and content.
    """
    # Start with the base text content from the current node
    message_contents = [
        MessageContent(type=MessageContentTypeEnum.text, text=node.data.get("prompt"))
    ]

    # Concurrently process files from the previous node if it's a FILE_PROMPT
    if previousNode and previousNode.type == MessageTypeEnum.FILE_PROMPT:
        files_to_process = previousNode.data.get("files", [])

        # Create a list of concurrent tasks
        tasks: list[Coroutine[Any, Any, MessageContent | None]] = [
            _create_message_content_from_file(pg_engine, file_info, add_file_content)
            for file_info in files_to_process
        ]

        # Run tasks concurrently and gather results
        file_contents = await asyncio.gather(*tasks)

        # Add the valid, processed file contents to the message
        message_contents.extend(content for content in file_contents if content)

    return Message(
        role=MessageRoleEnum.user,
        content=message_contents,
        node_id=node.id,
        type=node.type,
    )


def text_to_text_message_builder(
    node: Node,
) -> Message:
    """
    Builds a message object from a text-to-text node.

    Args:
        text (str): The text content of the message.
        node_id (str | None, optional): The ID of the node associated with the message.
        model (str | None, optional): The model used for generating the message.

    Returns:
        Message: A Message object with the user role and the provided text.
    """
    return Message(
        role=MessageRoleEnum.assistant,
        content=[
            MessageContent(
                type=MessageContentTypeEnum.text,
                text=node.data.get("reply"),
            )
        ],
        model=node.data.get("model"),
        node_id=node.id,
        type=node.type,
        usageData=node.data.get("usageData", None),
    )


def parallelization_message_builder(node: Node) -> Message:
    """
    Builds a message object from a parallelization node.

    Args:
        node (Node): The node to build the message for.
        system_prompt (str | None, optional): The system prompt to include in the message.

    Returns:
        Message: A Message object with the user role and the node's name as content.
    """

    # First we calculate the total cost and token usage for the message
    aggregatorUsageData = node.data.get("usageData", None)
    if aggregatorUsageData:
        for model in node.data.get("models", []):
            modelUsageData = model.get("usageData", {})
            for key in ["cost", "total_tokens", "prompt_tokens", "completion_tokens"]:
                aggregatorUsageData[key] = aggregatorUsageData.get(
                    key, 0
                ) + modelUsageData.get(key, 0)

    return Message(
        role=MessageRoleEnum.assistant,
        content=[
            MessageContent(
                type=MessageContentTypeEnum.text,
                text=node.data.get("aggregator").get("reply"),
            )
        ],
        model=node.data.get("aggregator").get("model"),
        node_id=node.id,
        type=node.type,
        data=node.data.get("models"),
        usageData=aggregatorUsageData,
    )


async def node_to_message(
    node: Node,
    previousNode: Node | None = None,
    add_file_content: bool = True,
    pg_engine: SQLAlchemyAsyncEngine | None = None,
) -> Message | None:
    """
    Convert a node to a message format.

    Args:
        node (Node): The node to convert.

    Returns:
        Message | None: A Message object representing the node, or None if the node type is not supported.
    """

    match node.type:
        case MessageTypeEnum.PROMPT:
            return await prompt_message_builder(
                pg_engine, node, previousNode, add_file_content
            )
        case MessageTypeEnum.TEXT_TO_TEXT:
            return text_to_text_message_builder(node)
        case MessageTypeEnum.PARALLELIZATION:
            return parallelization_message_builder(node)
        case MessageTypeEnum.FILE_PROMPT:
            return None
        case _:
            raise ValueError(f"Unsupported node type: {node.type}")


def get_first_user_prompt(messages: list[Message]) -> Message | None:
    """
    Get the first user prompt from a list of messages.

    Args:
        messages (list[Message]): The list of messages to search.

    Returns:
        Message | None: The first user prompt message, or None if not found.
    """
    return next(
        (
            msg
            for msg in messages
            if msg.role == MessageRoleEnum.user and msg.type == MessageTypeEnum.PROMPT
        ),
        None,
    )
