from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
import pybase64 as base64
from pathlib import Path
from enum import Enum
import re
import asyncio
from typing import Coroutine, Any

from database.pg.models import Node, Files
from database.neo4j.crud import NodeRecord

from models.message import (
    Message,
    MessageRoleEnum,
    MessageContent,
    MessageContentTypeEnum,
    MessageContentFile,
    MessageContentImageURL,
    NodeTypeEnum,
    IMG_EXT_TO_MIME_TYPE,
)
from database.pg.file_ops.file_crud import get_file_by_id
from services.github import (
    CLONED_REPOS_BASE_DIR,
    get_file_content,
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


async def create_message_content_from_file(
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


class CleanTextOption(Enum):
    REMOVE_NOTHING = 0
    REMOVE_TAGS_ONLY = 1
    REMOVE_TAG_AND_TEXT = 2


def text_cleaner(text: str, clean_text: CleanTextOption) -> str:
    """
    Cleans the provided text based on the specified cleaning option.

    Args:
        text (str): The text to be cleaned.
        clean_text (CleanTextOption): The option specifying how to clean the text.

    Returns:
        str: The cleaned text.
    """

    match clean_text:
        case CleanTextOption.REMOVE_NOTHING:
            return text.strip() if text else ""
        case CleanTextOption.REMOVE_TAGS_ONLY:
            # Remove [THINK] and [!THINK] tags but keep the text inside
            return re.sub(r"\[THINK\]|\[!THINK\]", "", text).strip() if text else ""
        case CleanTextOption.REMOVE_TAG_AND_TEXT:
            # Remove [THINK] and [!THINK] tags along with the text inside
            return (
                re.sub(
                    r"\[THINK\][\s\S]*?\[!THINK\]", "", text, flags=re.DOTALL
                ).strip()
                if text
                else ""
            )
        case _:
            raise ValueError(f"Unsupported clean_text option: {clean_text}")


def text_to_text_message_builder(
    node: Node,
    clean_text: CleanTextOption,
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
                text=text_cleaner(node.data.get("reply"), clean_text),
            )
        ],
        model=node.data.get("model"),
        node_id=node.id,
        type=node.type,
        usageData=node.data.get("usageData", None),
    )


def parallelization_message_builder(node: Node, clean_text: CleanTextOption) -> Message:
    """
    Builds a message object from a parallelization node.

    Args:
        node (Node): The node to build the message for.
        system_prompt (str | None, optional): The system prompt to include in the message.

    Returns:
        Message: A Message object with the user role and the node's name as content.
    """

    aggregatorUsageData = node.data.get("aggregator").get("usageData", None)

    return Message(
        role=MessageRoleEnum.assistant,
        content=[
            MessageContent(
                type=MessageContentTypeEnum.text,
                text=text_cleaner(node.data.get("aggregator").get("reply"), clean_text),
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
    clean_text: CleanTextOption = CleanTextOption.REMOVE_NOTHING,
) -> Message | None:
    """
    Convert a node to a message format.

    Args:
        node (Node): The node to convert.

    Returns:
        Message | None: A Message object representing the node, or None if the node type is not supported.
    """

    match node.type:
        case NodeTypeEnum.TEXT_TO_TEXT | NodeTypeEnum.ROUTING:
            return text_to_text_message_builder(node, clean_text)
        case NodeTypeEnum.PARALLELIZATION:
            return parallelization_message_builder(node, clean_text)
        case NodeTypeEnum.FILE_PROMPT | NodeTypeEnum.GITHUB | NodeTypeEnum.PROMPT:
            return None
        case _:
            raise ValueError(f"Unsupported node type: {node.type}")


def extract_context_prompt(
    connected_nodes: list[NodeRecord], connected_nodes_data: list[Node]
):
    """Given connected nodes and their data, extract the complete context prompt.

    Args:
        connected_nodes (list[NodeRecord]): The connected nodes to consider.
        connected_nodes_data (list[Node]): The data for the connected nodes.

    Returns:
        str: The complete context prompt.
    """
    connected_prompt_nodes = sorted(
        (node for node in connected_nodes if node.type == NodeTypeEnum.PROMPT),
        key=lambda x: -x.distance,
    )
    base_prompt = ""
    for node in connected_prompt_nodes:
        node_data = next((n for n in connected_nodes_data if n.id == node.id), None)
        if node_data:
            base_prompt += f"{node_data.data.get('prompt', '')} \n "

    return base_prompt


def extract_context_github(
    connected_nodes: list[NodeRecord], connected_nodes_data: list[Node]
):
    """Given connected nodes and their data, extract the GitHub context.

    Args:
        connected_nodes (list[NodeRecord]): The connected nodes to consider.
        connected_nodes_data (list[Node]): The data for the connected nodes.

    Returns:
        str: The complete GitHub context.
    """
    connected_github_nodes = sorted(
        (node for node in connected_nodes if node.type == NodeTypeEnum.GITHUB),
        key=lambda x: -x.distance,
    )
    file_prompt = ""
    file_format = "\n--- Start of file: {filename} ---\n{file_content}\n--- End of file: {filename} ---\n"
    for node in connected_github_nodes:
        node_data = next((n for n in connected_nodes_data if n.id == node.id), None)
        files = node_data.data.get("files", [])
        repo_data = node_data.data.get("repo", "")

        repo_dir = CLONED_REPOS_BASE_DIR / repo_data["full_name"]

        for file in files:
            file_content = get_file_content(repo_dir / file["path"])
            file_prompt += file_format.format(
                filename=f"{repo_data['full_name']}/{file['path']}",
                file_content=file_content,
            )

    return file_prompt


async def extract_context_attachment(
    connected_nodes: list[NodeRecord],
    connected_nodes_data: list[Node],
    pg_engine: SQLAlchemyAsyncEngine,
    add_file_content: bool,
):
    """Extracts context from attachment nodes.

    Args:
        connected_nodes (list[NodeRecord]): The connected nodes to consider.
        connected_nodes_data (list[Node]): The data for the connected nodes.
        pg_engine (SQLAlchemyAsyncEngine): The asynchronous SQLAlchemy engine for PostgreSQL database access.
        add_file_content (bool): Whether to include file content in the message.
    """
    connected_file_prompt_nodes = sorted(
        (node for node in connected_nodes if node.type == NodeTypeEnum.FILE_PROMPT),
        key=lambda x: -x.distance,
    )
    for node in connected_file_prompt_nodes:
        node_data = next((n for n in connected_nodes_data if n.id == node.id), None)
        files_to_process = node_data.data.get("files", [])

        tasks: list[Coroutine[Any, Any, MessageContent | None]] = [
            create_message_content_from_file(pg_engine, file_info, add_file_content)
            for file_info in files_to_process
        ]

        file_contents = await asyncio.gather(*tasks)

        return (content for content in file_contents if content)
    return []


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
            if msg.role == MessageRoleEnum.user and msg.type == NodeTypeEnum.PROMPT
        ),
        None,
    )
