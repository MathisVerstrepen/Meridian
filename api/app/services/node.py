import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Coroutine

import httpx
from const.extension_map import EXTENSION_MAP, FILENAME_MAP
from database.neo4j.crud import NodeRecord
from database.pg.chat_ops import get_tool_calls_by_ids
from database.pg.file_ops.file_crud import get_file_by_id
from database.pg.models import Node
from database.pg.token_ops.provider_token_crud import get_provider_token
from models.github import PRExtendedContext
from models.message import (
    Message,
    MessageContent,
    MessageContentFile,
    MessageContentImageURL,
    MessageContentTypeEnum,
    MessageRoleEnum,
    NodeTypeEnum,
)
from services.crypto import decrypt_api_key
from services.file_encoding import encode_file_as_data_uri
from services.files import get_or_calculate_file_hash, get_user_storage_path
from services.git_service import (
    build_github_auth_env,
    build_gitlab_auth_env,
    get_files_content_for_branch,
    pull_repo,
)
from services.github import get_github_pr_extended_context, get_github_token_from_db, get_pr_diff
from services.gitlab_api_service import get_gitlab_mr_extended_context, get_mr_diff
from services.gitlab_provider import build_gitlab_provider_key, get_gitlab_instance_url
from services.repository_paths import build_repo_path
from services.tool_calls import expand_tool_context_in_text, extract_tool_call_ids
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
                    text=f"<system>\n{system_prompt}\n</system>",
                )
            ],
        )
        if system_prompt
        else None
    )


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

    file_hash = await get_or_calculate_file_hash(pg_engine, file_id, user_id, str(file_path))

    if content_type == "application/pdf":
        if not add_file_content:
            file_data = file_path.name
        else:
            file_data = encode_file_as_data_uri(file_path, content_type)

        return MessageContent(
            type=MessageContentTypeEnum.file,
            file=MessageContentFile(
                filename=file_record.name,
                file_data=file_data,
                id=str(file_record.id),
                hash=file_hash,
            ),
        )
    elif content_type.startswith("image/"):
        if not add_file_content:
            file_data = file_path.name
        else:
            file_data = encode_file_as_data_uri(file_path, content_type)

        return MessageContent(
            type=MessageContentTypeEnum.image_url,
            image_url=MessageContentImageURL(url=file_data, id=str(file_record.id)),
        )

    try:
        content = "[Content omitted]"

        return MessageContent(
            type=MessageContentTypeEnum.text,
            text=f"--- Start of file: {file_record.name} ---\n{content}\n--- End of file: {file_record.name} ---\n",  # noqa: E501
        )
    except Exception:
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


async def maybe_expand_tool_context(
    text: str,
    pg_engine: SQLAlchemyAsyncEngine | None,
    user_id: str | None,
    expand_tool_context: bool,
) -> str:
    if not expand_tool_context or not text or pg_engine is None or user_id is None:
        return text

    tool_call_ids = extract_tool_call_ids(text)
    if not tool_call_ids:
        return text

    tool_calls_by_id = await get_tool_calls_by_ids(
        pg_engine,
        tool_call_ids=tool_call_ids,
        user_id=user_id,
    )
    if not tool_calls_by_id:
        return text

    return expand_tool_context_in_text(text, tool_calls_by_id)


async def text_to_text_message_builder(
    node: Node,
    clean_text: CleanTextOption,
    *,
    pg_engine: SQLAlchemyAsyncEngine | None = None,
    user_id: str | None = None,
    expand_tool_context: bool = False,
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
    reply = await maybe_expand_tool_context(reply, pg_engine, user_id, expand_tool_context)
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


async def parallelization_message_builder(
    node: Node,
    clean_text: CleanTextOption,
    *,
    pg_engine: SQLAlchemyAsyncEngine | None = None,
    user_id: str | None = None,
    expand_tool_context: bool = False,
) -> Message:
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
    aggregator_reply = await maybe_expand_tool_context(
        aggregator.get("reply", ""),
        pg_engine,
        user_id,
        expand_tool_context,
    )

    return Message(
        role=MessageRoleEnum.assistant,
        content=[
            MessageContent(
                type=MessageContentTypeEnum.text,
                text=text_cleaner(aggregator_reply, clean_text),
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
    *,
    pg_engine: SQLAlchemyAsyncEngine | None = None,
    user_id: str | None = None,
    expand_tool_context: bool = False,
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
            return await text_to_text_message_builder(
                node,
                clean_text,
                pg_engine=pg_engine,
                user_id=user_id,
                expand_tool_context=expand_tool_context,
            )
        case NodeTypeEnum.PARALLELIZATION:
            return await parallelization_message_builder(
                node,
                clean_text,
                pg_engine=pg_engine,
                user_id=user_id,
                expand_tool_context=expand_tool_context,
            )
        case NodeTypeEnum.FILE_PROMPT | NodeTypeEnum.GITHUB | NodeTypeEnum.PROMPT:
            return None
        case _:
            raise ValueError(f"Unsupported node type: {node.type}")


def extract_context_prompt(
    connected_nodes: list[NodeRecord],
    connected_nodes_data: list[Node],
    add_separators: bool = False,
):
    """Given connected nodes and their data, extract the complete context prompt.

    Args:
        connected_nodes (list[NodeRecord]): The connected nodes to consider.
        connected_nodes_data (list[Node]): The data for the connected nodes.
        add_separators (bool): Whether to add separators with node IDs before each node content.

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
            if add_separators:
                base_prompt += f"--- Node ID: {node.id} ---\n"
            base_prompt += f"{node_data.data.get('prompt', '')} \n"

    return base_prompt


@dataclass
class RepoContextRequest:
    repo_dir: Path
    branch: str
    repo_full_name: str
    provider: str
    files: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    repo_data: dict = field(default_factory=dict)


def _parse_github_nodes(
    connected_nodes: list[NodeRecord], connected_nodes_data: list[Node]
) -> list[RepoContextRequest]:
    """Parses connected GitHub nodes into a list of context requests."""
    connected_github_nodes = sorted(
        (node for node in connected_nodes if node.type == NodeTypeEnum.GITHUB),
        key=lambda x: -x.distance,
    )

    requests = []
    for node in connected_github_nodes:
        node_data = next((n for n in connected_nodes_data if n.id == node.id), None)
        if not (node_data and isinstance(node_data.data, dict)):
            continue

        branch = node_data.data.get("branch", "main")
        files = node_data.data.get("files", [])
        issues = node_data.data.get("selectedIssues", [])
        repo_data = node_data.data.get("repo", "")

        if not isinstance(repo_data, dict):
            continue

        full_name = repo_data.get("full_name", "")
        provider = repo_data.get("provider", "github")
        try:
            repo_dir = build_repo_path(provider, full_name, require_git_repo=False)
        except ValueError:
            continue

        requests.append(
            RepoContextRequest(
                repo_dir=repo_dir,
                branch=branch,
                repo_full_name=full_name,
                provider=provider,
                files=files,
                issues=issues,
                repo_data=repo_data,
            )
        )
    return requests


async def _build_git_auth_env(
    provider: str,
    user_id: str,
    pg_engine: SQLAlchemyAsyncEngine,
    token_cache: dict[str, str | None],
) -> dict | None:
    token = token_cache.get(provider)
    if provider not in token_cache:
        try:
            if provider == "github":
                token = await get_github_token_from_db(pg_engine, user_id)
            elif provider.startswith("gitlab:"):
                instance_url = get_gitlab_instance_url(provider)
                rec = await get_provider_token(
                    pg_engine, user_id, build_gitlab_provider_key(instance_url)
                )
                if rec:
                    data = json.loads(rec.access_token)
                    token = await decrypt_api_key(data["pat"])
        except Exception:
            token = None
        token_cache[provider] = token

    if not token:
        return None

    if provider == "github":
        return build_github_auth_env(token)

    if provider.startswith("gitlab:"):
        return build_gitlab_auth_env(get_gitlab_instance_url(provider), token)

    return None


async def _sync_repositories(
    requests: list[RepoContextRequest], user_id: str, pg_engine: SQLAlchemyAsyncEngine
):
    """Pulls the latest changes for all requested repositories and branches."""
    repos_to_pull: dict[tuple[Path, str, str], None] = {}
    for req in requests:
        repos_to_pull[(req.repo_dir, req.branch, req.provider)] = None

    token_cache: dict[str, str | None] = {}
    pull_tasks = []
    for repo_dir, branch, provider in repos_to_pull.keys():
        auth_env = await _build_git_auth_env(provider, user_id, pg_engine, token_cache)
        pull_tasks.append(pull_repo(repo_dir, branch, env=auth_env))

    if pull_tasks:
        await asyncio.gather(*pull_tasks)


async def _fetch_local_file_contents(
    requests: list[RepoContextRequest], add_file_content: bool
) -> dict[Path, dict[str, dict[str, str]]]:
    """
    Reads file contents from local clones.
    Returns a map: {repo_dir: {branch: {file_path: content}}}
    """
    if not add_file_content:
        return {}

    # Group files by (repo_dir, branch)
    files_to_read: dict[tuple[Path, str], set[str]] = {}
    for req in requests:
        key = (req.repo_dir, req.branch)
        if key not in files_to_read:
            files_to_read[key] = set()
        for file in req.files:
            files_to_read[key].add(file["path"])

    # Create batch read tasks
    read_tasks = []
    task_keys = []
    for (repo_dir, branch), paths_set in files_to_read.items():
        if paths_set:
            read_tasks.append(get_files_content_for_branch(repo_dir, branch, list(paths_set)))
            task_keys.append((repo_dir, branch))

    if not read_tasks:
        return {}

    all_contents_list = await asyncio.gather(*read_tasks)

    # Map results
    result_map: dict[Path, dict[str, dict[str, str]]] = {}
    for i, (repo_dir, branch) in enumerate(task_keys):
        if repo_dir not in result_map:
            result_map[repo_dir] = {}
        result_map[repo_dir][branch] = all_contents_list[i]

    return result_map


async def _fetch_remote_diffs_and_context(
    requests: list[RepoContextRequest],
    user_id: str,
    pg_engine: SQLAlchemyAsyncEngine,
    add_file_content: bool,
    git_http_client: httpx.AsyncClient,
) -> tuple[dict[tuple[str, int], str], dict[tuple[str, int], PRExtendedContext]]:
    """
    Fetches diffs AND extended context (comments, commits, checks) for selected PRs/Issues.
    Returns: (diffs_map, extended_context_map)
    """
    if not add_file_content:
        return {}, {}

    diff_task_map = {}
    context_task_map = {}
    token_cache: dict[str, str | None] = {}

    for req in requests:
        if not req.issues:
            continue

        # Resolve Token
        token = token_cache.get(req.provider)
        if not token and req.provider not in token_cache:
            try:
                if req.provider == "github":
                    token = await get_github_token_from_db(pg_engine, user_id)
                elif req.provider.startswith("gitlab:"):
                    rec = await get_provider_token(
                        pg_engine,
                        user_id,
                        build_gitlab_provider_key(get_gitlab_instance_url(req.provider)),
                    )
                    if rec:
                        data = json.loads(rec.access_token)
                        token = await decrypt_api_key(data["pat"])
            except Exception:
                token = None
            token_cache[req.provider] = token

        token = token_cache.get(req.provider)
        if not token:
            continue

        # Create Tasks
        for issue in req.issues:
            if issue.get("is_pull_request"):
                number = issue.get("number")
                if not number:
                    continue

                key = (req.repo_full_name, number)
                if key in diff_task_map:
                    continue

                if req.provider == "github":
                    diff_task_map[key] = get_pr_diff(
                        token,
                        req.repo_full_name,
                        number,
                        http_client=git_http_client,
                    )
                    context_task_map[key] = get_github_pr_extended_context(
                        token,
                        req.repo_full_name,
                        number,
                        http_client=git_http_client,
                    )
                elif req.provider.startswith("gitlab:"):
                    instance_url = get_gitlab_instance_url(req.provider)
                    diff_task_map[key] = get_mr_diff(
                        token,
                        instance_url,
                        req.repo_full_name,
                        number,
                        http_client=git_http_client,
                    )
                    context_task_map[key] = get_gitlab_mr_extended_context(
                        token,
                        instance_url,
                        req.repo_full_name,
                        number,
                        http_client=git_http_client,
                    )

    if not diff_task_map:
        return {}, {}

    # Execute Diff Tasks
    diff_keys = list(diff_task_map.keys())
    diff_tasks = list(diff_task_map.values())

    context_keys = list(context_task_map.keys())
    context_tasks = list(context_task_map.values())

    semaphore = asyncio.Semaphore(5)

    async def limited_task(task):
        async with semaphore:
            return await task

    all_tasks = [limited_task(task) for task in diff_tasks + context_tasks]
    all_results = await asyncio.gather(*all_tasks)

    # Split results
    num_diffs = len(diff_tasks)
    diff_results = all_results[:num_diffs]
    context_results = all_results[num_diffs:]

    diffs_map: dict[tuple[str, int], str] = {k: str(v) for k, v in zip(diff_keys, diff_results)}
    context_map: dict[tuple[str, int], PRExtendedContext] = {
        k: v for k, v in zip(context_keys, context_results)  # type: ignore[misc]
    }

    return diffs_map, context_map


def _format_github_context(
    requests: list[RepoContextRequest],
    file_contents_map: dict[Path, dict[str, dict[str, str]]],
    diffs_map: dict[tuple[str, int], str],
    context_map: dict[tuple[str, int], PRExtendedContext],
    add_file_content: bool,
) -> str:
    """Formats the gathered data into the final context string."""
    final_prompt = ""

    file_format = "\n--- Start of file: {filename} ---\n```{language}\n{file_content}\n```\n--- End of file: {filename} ---\n"  # noqa: E501
    issue_format = (
        "\n--- Start of {type} #{number}: {title} ---\n"
        "Author: {author}\n"
        "State: {state}\n"
        "Link: {url}\n\n"
        "{body}\n"
        "{checks_section}"
        "{commits_section}"
        "{comments_section}"
        "{diff_section}\n"
        "--- End of {type} ---\n"
    )

    for req in requests:
        # 1. Format Files
        provider_prefix = "gitlab" if "gitlab" in str(req.repo_dir) else "github"
        contents_for_branch = file_contents_map.get(req.repo_dir, {}).get(req.branch, {})

        for file in req.files:
            path = file["path"]
            content = contents_for_branch.get(path)

            # Determine language
            path_obj = Path(path)
            file_name = path_obj.name.lower()
            file_ext = path_obj.suffix.lower()
            language = FILENAME_MAP.get(file_name) or EXTENSION_MAP.get(file_ext, "")

            if content is not None or not add_file_content:
                filename = (
                    f"{req.repo_full_name}/{path}"
                    if add_file_content
                    else f"{provider_prefix}/{req.repo_full_name}/{path}"
                )
                final_prompt += file_format.format(
                    filename=filename,
                    language=language,
                    file_content=content if add_file_content else "[Content omitted]",
                )

        # 2. Format Issues & PRs
        for issue in req.issues:
            issue_type = "Pull Request" if issue.get("is_pull_request") else "Issue"
            body_content = issue.get("body") or "[No description provided]"
            if not add_file_content:
                body_content = "[Content omitted]"

            diff_section = ""
            checks_section = ""
            commits_section = ""
            comments_section = ""

            if issue.get("is_pull_request") and add_file_content:
                issue_number = issue.get("number")
                if issue_number is not None:
                    # Diff
                    diff_text = diffs_map.get((req.repo_full_name, issue_number))
                    if diff_text:
                        diff_section = f"\n--- Diff ---\n{diff_text}\n"

                    # Extended Context
                    ext_ctx = context_map.get((req.repo_full_name, issue_number))
                    if ext_ctx:
                        # Checks
                        if ext_ctx.checks:
                            checks_list = "\n".join(
                                [
                                    f"- {c.name}: {c.conclusion or c.status}"
                                    for c in ext_ctx.checks[:10]
                                ]
                            )
                            checks_section = f"\n[CI/CD Status]\n{checks_list}\n"

                        # Commits
                        if ext_ctx.commits:
                            commits_list = "\n".join(
                                [
                                    f"- {c.sha[:7]}: {c.message.splitlines()[0]} ({c.author_name})"
                                    for c in ext_ctx.commits[:10]
                                ]
                            )
                            commits_section = f"\n[Recent Commits]\n{commits_list}\n"

                        # Comments
                        if ext_ctx.comments:
                            comments_list = ""
                            for c in ext_ctx.comments[-20:]:  # Last 20 comments
                                loc = f" ({c.path}:{c.line})" if c.path and c.line else ""
                                comments_list += f"- {c.user_login}{loc}: {c.body}\n"
                            comments_section = f"\n[Review Comments]\n{comments_list}"

            final_prompt += issue_format.format(
                type=issue_type,
                number=issue.get("number"),
                title=issue.get("title"),
                author=issue.get("user_login"),
                state=issue.get("state"),
                url=issue.get("html_url"),
                body=body_content,
                checks_section=checks_section,
                commits_section=commits_section,
                comments_section=comments_section,
                diff_section=diff_section,
            )

    return final_prompt


async def extract_context_github(
    connected_nodes: list[NodeRecord],
    connected_nodes_data: list[Node],
    github_auto_pull: bool,
    add_file_content: bool,
    user_id: str,
    pg_engine: SQLAlchemyAsyncEngine,
    git_http_client: httpx.AsyncClient,
):
    """
    Extracts context from GitHub nodes by pulling repositories, reading specified files,
    and fetching selected Issues/PRs.

    Args:
        connected_nodes (list[NodeRecord]): The connected nodes to consider.
        connected_nodes_data (list[Node]): The data for the connected nodes.
        github_auto_pull (bool): Whether to auto-pull changes from remote.
        add_file_content (bool): Whether to include actual file/diff text.
        user_id (str): The current user ID.
        pg_engine (SQLAlchemyAsyncEngine): Database engine.

    Returns:
        str: The complete GitHub context.
    """
    # 1. Parse Nodes
    requests = _parse_github_nodes(connected_nodes, connected_nodes_data)
    if not requests:
        return ""

    # 2. Sync Repositories (Concurrent Pull)
    if github_auto_pull:
        await _sync_repositories(requests, user_id, pg_engine)

    # 3. Fetch Content (Files locally, Diffs & Context remotely)
    file_contents_task = _fetch_local_file_contents(requests, add_file_content)
    remote_data_task = _fetch_remote_diffs_and_context(
        requests, user_id, pg_engine, add_file_content, git_http_client
    )

    file_contents_map, (diffs_map, context_map) = await asyncio.gather(
        file_contents_task, remote_data_task
    )

    # 4. Format Output
    return _format_github_context(
        requests, file_contents_map, diffs_map, context_map, add_file_content
    )


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

        for content in file_contents:
            if content:
                # Inject the ID into the text stream so the LLM can see it for tool calls
                if (
                    content.type == MessageContentTypeEnum.image_url
                    and content.image_url
                    and content.image_url.id
                ):
                    final_content.append(
                        MessageContent(
                            type=MessageContentTypeEnum.text,
                            text=f"Image ID: {content.image_url.id}",
                        )
                    )
                final_content.append(content)

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
