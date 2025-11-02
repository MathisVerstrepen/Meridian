import asyncio
import logging
import os
from asyncio import Semaphore

import httpx
from const.prompts import CONTEXT_MERGER_SUMMARY_PROMPT
from database.neo4j.crud import NodeRecord, get_immediate_parents
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids, update_node_data
from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate
from models.context_merger import ContextMergerConfig, ContextMergerMode
from models.message import (
    Message,
    MessageContent,
    MessageContentTypeEnum,
    MessageRoleEnum,
    NodeTypeEnum,
)
from neo4j import AsyncDriver
from services.node import CleanTextOption, system_message_builder
from services.openrouter import OpenRouterReqChat, make_openrouter_request_non_streaming
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")


class ContextMergerService:
    """
    A service dedicated to handling the logic of ContextMerger nodes.
    """

    def __init__(
        self,
        pg_engine: SQLAlchemyAsyncEngine,
        neo4j_driver: AsyncDriver,
        graph_id: str,
        user_id: str,
    ):
        self.pg_engine = pg_engine
        self.neo4j_driver = neo4j_driver
        self.graph_id = graph_id
        self.user_id = user_id

    async def _generate_summary_text(self, raw_text: str, merger_node_id: str) -> str:
        """Generates a summary for a given text using a dedicated model."""
        from services.graph_service import get_effective_graph_config

        graph_config, _, open_router_api_key = await get_effective_graph_config(
            pg_engine=self.pg_engine, graph_id=self.graph_id, user_id=self.user_id
        )
        summarizer_config = GraphConfigUpdate()
        system_message = system_message_builder(CONTEXT_MERGER_SUMMARY_PROMPT)
        if not system_message:
            return "Error: Could not generate summary due to a missing system prompt."

        user_message = Message(
            role=MessageRoleEnum.user,
            content=[MessageContent(type=MessageContentTypeEnum.text, text=raw_text)],
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as http_client:
                req = OpenRouterReqChat(
                    api_key=open_router_api_key,
                    model="openai/gpt-oss-120b",
                    messages=[system_message, user_message],
                    config=summarizer_config,
                    user_id=self.user_id,
                    pg_engine=self.pg_engine,
                    node_id=merger_node_id,
                    graph_id=self.graph_id,
                    stream=False,
                    http_client=http_client,
                    pdf_engine=graph_config.pdf_engine,
                )
                return await make_openrouter_request_non_streaming(req, self.pg_engine)
        except Exception as e:
            logger.error(f"Error during summary generation: {e}")
            return f"Error: Could not generate summary. {e}"

    async def _get_branch_histories(
        self, parent_branch_heads: list[NodeRecord], github_auto_pull: bool
    ) -> list[list[Message]]:
        """Fetches conversation histories for all parent branches in parallel."""
        from services.graph_service import construct_message_history

        semaphore = Semaphore(int(os.getenv("DATABASE_POOL_SIZE", "10")) // 2)

        async def get_branch_history(branch_head_node: NodeRecord) -> list[Message]:
            async with semaphore:
                branch_history = await construct_message_history(
                    pg_engine=self.pg_engine,
                    neo4j_driver=self.neo4j_driver,
                    graph_id=self.graph_id,
                    user_id=self.user_id,
                    node_id=branch_head_node.id,
                    system_prompt="",
                    add_current_node=True,
                    view="full",
                    clean_text=CleanTextOption.REMOVE_TAG_AND_TEXT,
                    github_auto_pull=github_auto_pull,
                )
                return [msg for msg in branch_history if msg.role != MessageRoleEnum.system]

        tasks = [get_branch_history(head) for head in parent_branch_heads]
        return await asyncio.gather(*tasks)

    def _format_branch_text(
        self, history: list[Message], branch_index: int, mode: ContextMergerMode
    ) -> str:
        """Formats the text content of a branch for merging or summarization."""
        parts = [
            "<title>Merged Context from Previous Conversation Branch</title>",
            f'<branch index="{branch_index + 1}">',
        ]
        for message in history:
            parts.append(f'<message role="{message.role.value}">')
            content_parts = [
                item.text.strip()
                for item in message.content
                if item.type == MessageContentTypeEnum.text and item.text
            ]
            parts.append(f"<content>{' '.join(content_parts)}</content>")
            parts.append("</message>")
        parts.append("</branch>")
        return "".join(parts)

    def _format_summaries_text(self, summaries: list[str]) -> str:
        """Formats the summaries of branches for merging."""
        parts = ["<title>Merged Summarized Context from Previous Conversation Branches</title>"]
        for i, summary in enumerate(summaries):
            parts.append(f'<branch index="{i + 1}">')
            parts.append(f"<summary>{summary}</summary>")
            parts.append("</branch>")
        return "".join(parts)

    async def _merge_branches_summary_mode(
        self,
        branch_histories: list[list[Message]],
        parent_branch_heads: list[NodeRecord],
        config: ContextMergerConfig,
        merger_node_id: str,
    ) -> tuple[str, dict[str, str]]:
        """Handles the 'summary' merge mode, generating and caching summaries."""
        summaries_map = config.branch_summaries.copy()
        final_summaries = ["" for _ in branch_histories]
        tasks_to_run, task_metadata = [], []

        for i, history in enumerate(branch_histories):
            branch_id = parent_branch_heads[i].id
            if cached_summary := summaries_map.get(branch_id):
                final_summaries[i] = cached_summary
            else:
                raw_text = self._format_branch_text(history, i, ContextMergerMode.SUMMARY)
                tasks_to_run.append(self._generate_summary_text(raw_text, merger_node_id))
                task_metadata.append((i, branch_id))

        if tasks_to_run:
            generated_summaries = await asyncio.gather(*tasks_to_run)
            for summary, (index, branch_id) in zip(generated_summaries, task_metadata):
                final_summaries[index] = summary
                summaries_map[branch_id] = summary

            await update_node_data(
                self.pg_engine, self.graph_id, merger_node_id, {"branch_summaries": summaries_map}
            )

        return self._format_summaries_text(final_summaries), summaries_map

    def _merge_branches_full_or_last_n_mode(
        self, branch_histories: list[list[Message]], config: ContextMergerConfig
    ) -> str:
        """Handles 'full' and 'last_n' merge modes."""
        aggregated_texts = []
        for i, history in enumerate(branch_histories):
            if config.mode == ContextMergerMode.LAST_N:
                history = history[-config.last_n :]
            aggregated_texts.append(self._format_branch_text(history, i, config.mode))
        return "\n\n".join(aggregated_texts)

    async def construct_merged_history(
        self, merger_node_id: str, system_prompt: str, github_auto_pull: bool
    ) -> list[Message]:
        """
        Main entry point to construct a merged message history from multiple branches.
        The resulting user message will contain metadata about branch summaries if applicable.
        """

        # 1. Fetch the ContextMerger node to get its configuration
        merger_nodes = await get_nodes_by_ids(self.pg_engine, self.graph_id, [merger_node_id])
        if not merger_nodes:
            raise ValueError(f"ContextMerger node with ID {merger_node_id} not found.")

        # 2. Get immediate parent nodes (branch heads) and their histories
        node_data = merger_nodes[0].data
        config = ContextMergerConfig.from_node_data(node_data)  # type: ignore
        parent_heads = await get_immediate_parents(self.neo4j_driver, self.graph_id, merger_node_id)
        branch_histories = await self._get_branch_histories(parent_heads, github_auto_pull)

        # 3. Merge histories according to the specified mode
        final_text, metadata = "", {}
        if config.mode == ContextMergerMode.SUMMARY:
            final_text, summaries = await self._merge_branches_summary_mode(
                branch_histories, parent_heads, config, merger_node_id
            )
            metadata = {"branch_summaries": summaries}
        else:
            final_text = self._merge_branches_full_or_last_n_mode(branch_histories, config)

        # 4. Construct the final merged user message
        merged_user_message = Message(
            role=MessageRoleEnum.user,
            content=[MessageContent(type=MessageContentTypeEnum.text, text=final_text)],
            type=NodeTypeEnum.CONTEXT_MERGER,
            node_id=merger_node_id,
            metadata=metadata if metadata.get("branch_summaries") else None,
        )

        final_messages = []
        if system_msg := system_message_builder(system_prompt):
            final_messages.append(system_msg)
        final_messages.append(merged_user_message)

        return final_messages
