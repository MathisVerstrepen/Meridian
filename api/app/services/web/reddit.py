import logging

logger = logging.getLogger("uvicorn.error")


def _format_comment_thread(comment_node: dict, depth: int) -> str:
    """
    Recursively formats a Reddit comment and its replies into a Markdown string.

    Args:
        comment_node: The JSON object for a single comment.
        depth: The current nesting level of the comment.

    Returns:
        A formatted Markdown string for the comment thread.
    """
    if comment_node.get("kind") != "t1":
        return ""  # Ignore "more" objects

    data = comment_node.get("data", {})
    author = data.get("author", "[deleted]")
    body = data.get("body", "[deleted]").strip()
    score = data.get("score", 0)

    if not body:
        return ""

    # Use '>' for indentation to represent nesting
    indent = "> " * (depth + 1)

    # Format the current comment
    comment_md = f"{indent}**u/{author}** ({score} points)\n"
    # Ensure all lines in the comment body are indented
    comment_md += f"{indent}" + body.replace("\n", f"\n{indent}") + "\n\n"

    # Recursively process replies
    replies_node = data.get("replies")
    if replies_node and isinstance(replies_node, dict):
        for reply in replies_node.get("data", {}).get("children", []):
            comment_md += _format_comment_thread(reply, depth + 1)

    return comment_md


def _parse_reddit_json_to_markdown(data: list) -> str | None:
    """
    Parses the full JSON response from a Reddit thread into a clean Markdown summary.

    Args:
        data: The parsed JSON data from a Reddit .json URL.

    Returns:
        A string containing the formatted Markdown, or None if parsing fails.
    """
    try:
        post_data = data[0]["data"]["children"][0]["data"]
        comments_data = data[1]["data"]["children"]

        title = post_data.get("title", "No Title")
        author = post_data.get("author", "N/A")
        subreddit = post_data.get("subreddit_name_prefixed", "N/A")
        score = post_data.get("score", 0)
        num_comments = post_data.get("num_comments", 0)
        selftext = post_data.get("selftext", "").strip()
        is_self_post = post_data.get("is_self", False)
        permalink = "https://www.reddit.com" + post_data.get("permalink", "")

        # Build the post summary
        md_parts = [
            f"# {title}",
            f"**Subreddit:** {subreddit} | **Author:** u/{author} | **Upvotes:** {score} | **Comments:** {num_comments}",  # noqa: E501
            f"**Post URL:** <{permalink}>",
        ]

        # If it's a link post, add the external URL
        if not is_self_post:
            linked_url = post_data.get("url_overridden_by_dest") or post_data.get("url")
            if linked_url:
                md_parts.append(f"**Linked URL:** <{linked_url}>")

        md_parts.append("---")

        if selftext:
            md_parts.append(selftext)

        md_parts.append("\n## Comments\n")

        # Build the comment threads
        for comment_node in comments_data:
            md_parts.append(_format_comment_thread(comment_node, depth=0))

        return "\n".join(md_parts)

    except (IndexError, KeyError, TypeError) as e:
        logger.error(f"Could not parse Reddit JSON structure: {e}")
        return None
