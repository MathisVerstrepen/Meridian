import asyncio
import re
from enum import Enum
from pathlib import Path
from typing import Any, Coroutine

import pybase64 as base64
from database.neo4j.crud import NodeRecord
from database.pg.file_ops.file_crud import get_file_by_id
from database.pg.models import Node
from models.message import (
    Message,
    MessageContent,
    MessageContentFile,
    MessageContentImageURL,
    MessageContentTypeEnum,
    MessageRoleEnum,
    NodeTypeEnum,
)
from services.files import get_user_storage_path
from services.github import (
    CLONED_REPOS_BASE_DIR,
    fetch_repo,
    get_file_content_for_branch,
    pull_repo,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine


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
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, file_info: dict, add_file_content: bool
) -> MessageContent | None:
    """
    Fetches a file and creates a corresponding MessageContent object.
    Returns None if the file type is unsupported.
    """
    file_id = file_info.get("id")
    if file_id is None:
        return None
    file_record = await get_file_by_id(pg_engine=pg_engine, file_id=file_id, user_id=user_id)
    if not file_record:
        return None

    user_dir = get_user_storage_path(user_id)
    content_type = file_info.get("content_type", "")
    if not file_record.file_path:
        return None
    file_path = Path(user_dir) / file_record.file_path

    if not add_file_content:
        file_data = file_path.name
    else:
        file_data = _encode_file_as_data_uri(file_path, content_type)

    if content_type == "application/pdf":
        return MessageContent(
            type=MessageContentTypeEnum.file,
            file=MessageContentFile(filename=file_record.name, file_data=file_data),
        )
    elif content_type.startswith("image/"):
        return MessageContent(
            type=MessageContentTypeEnum.image_url,
            image_url=MessageContentImageURL(url=file_data, id=str(file_record.id)),
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
                re.sub(r"\[THINK\][\s\S]*?\[!THINK\]", "", text, flags=re.DOTALL).strip()
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
    reply = ""
    model = None
    usage_data = None
    if isinstance(node.data, dict):
        reply = str(node.data.get("reply", ""))
        model = node.data.get("model")
        usage_data = node.data.get("usageData", None)
    return Message(
        role=MessageRoleEnum.assistant,
        content=[
            MessageContent(
                type=MessageContentTypeEnum.text,
                text=text_cleaner(reply, clean_text),
            )
        ],
        model=model,
        node_id=node.id,
        type=NodeTypeEnum(node.type),
        usageData=usage_data,
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
    if not isinstance(node.data, dict):
        raise ValueError(f"Node data must be a dict for node type {node.type}")

    aggregator = node.data.get("aggregator", {})
    aggregatorUsageData = aggregator.get("usageData", None)

    return Message(
        role=MessageRoleEnum.assistant,
        content=[
            MessageContent(
                type=MessageContentTypeEnum.text,
                text=text_cleaner(aggregator.get("reply", ""), clean_text),
            )
        ],
        model=aggregator.get("model"),
        node_id=node.id,
        type=NodeTypeEnum(node.type),
        data=node.data.get("models", {}),
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
        Message | None: A Message object representing the node, or None if the node type is
            not supported.
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


def extract_context_prompt(connected_nodes: list[NodeRecord], connected_nodes_data: list[Node]):
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
        if node_data and isinstance(node_data.data, dict):
            base_prompt += f"{node_data.data.get('prompt', '')} \n "

    return base_prompt


async def extract_context_github(
    connected_nodes: list[NodeRecord], connected_nodes_data: list[Node], github_auto_pull: bool
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
    file_format = (
        "\n--- Start of file: {filename} ---\n{file_content}\n--- End of file: {filename} ---\n"
    )
    for node in connected_github_nodes:
        node_data = next((n for n in connected_nodes_data if n.id == node.id), None)
        if node_data and isinstance(node_data.data, dict):
            branch = node_data.data.get("branch", "main")
            files = node_data.data.get("files", [])
            repo_data = node_data.data.get("repo", "")

        repo_dir = CLONED_REPOS_BASE_DIR / repo_data["full_name"]

        if github_auto_pull:
            await pull_repo(repo_dir, branch)

        for file in files:
            file_content = await get_file_content_for_branch(repo_dir, branch, file["path"])
            file_prompt += file_format.format(
                filename=f"{repo_data['full_name']}/{file['path']}",
                file_content=file_content,
            )

    return file_prompt


async def extract_context_attachment(
    user_id: str,
    connected_nodes: list[NodeRecord],
    connected_nodes_data: list[Node],
    pg_engine: SQLAlchemyAsyncEngine,
    add_file_content: bool,
):
    """Extracts context from attachment nodes.

    Args:
        connected_nodes (list[NodeRecord]): The connected nodes to consider.
        connected_nodes_data (list[Node]): The data for the connected nodes.
        pg_engine (SQLAlchemyAsyncEngine): The asynchronous SQLAlchemy engine for PostgreSQL
            database access.
        add_file_content (bool): Whether to include file content in the message.
    """
    connected_file_prompt_nodes = sorted(
        (node for node in connected_nodes if node.type == NodeTypeEnum.FILE_PROMPT),
        key=lambda x: -x.distance,
    )
    final_content: list[MessageContent] = []
    for node in connected_file_prompt_nodes:
        node_data = next((n for n in connected_nodes_data if n.id == node.id), None)
        if node_data and isinstance(node_data.data, dict):
            files_to_process = node_data.data.get("files", [])

        tasks: list[Coroutine[Any, Any, MessageContent | None]] = [
            create_message_content_from_file(pg_engine, user_id, file_info, add_file_content)
            for file_info in files_to_process
        ]

        file_contents = await asyncio.gather(*tasks)

        final_content.extend(content for content in file_contents if content)
    return final_content


def get_first_user_prompt(messages: list[Message]) -> Message | None:
    """
    Get the first user prompt from a list of messages.

    Args:
        messages (list[Message]): The list of messages to search.

    Returns:
        Message | None: The first user prompt message, or None if not found.
    """
    return next(
        (msg for msg in messages if msg.role == MessageRoleEnum.user),
        None,
    )
