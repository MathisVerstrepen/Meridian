import logging
import warnings
from html import unescape
from urllib.parse import ParseResult, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning
from markdownify import markdownify as md

logger = logging.getLogger("uvicorn.error")

REDDIT_HOSTS = {"reddit.com", "www.reddit.com", "old.reddit.com"}
REDDIT_STRUCTURED_SUFFIXES = (".json", ".rss")


def _ensure_url_scheme(url: str) -> str:
    url = url.strip()
    if url.lower().startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def _is_reddit_url(url: str) -> bool:
    parsed_url = urlparse(_ensure_url_scheme(url))
    return parsed_url.netloc.lower() in REDDIT_HOSTS


def _has_structured_suffix(path: str, suffix: str) -> bool:
    normalized_path = path.rstrip("/").lower()
    return normalized_path.endswith(suffix)


def _is_reddit_json_url(url: str) -> bool:
    parsed_url = urlparse(_ensure_url_scheme(url))
    return _is_reddit_url(url) and _has_structured_suffix(parsed_url.path, ".json")


def _is_reddit_rss_url(url: str) -> bool:
    parsed_url = urlparse(_ensure_url_scheme(url))
    return _is_reddit_url(url) and _has_structured_suffix(parsed_url.path, ".rss")


def _is_reddit_structured_url(url: str) -> bool:
    parsed_url = urlparse(_ensure_url_scheme(url))
    return _is_reddit_url(url) and any(
        _has_structured_suffix(parsed_url.path, suffix) for suffix in REDDIT_STRUCTURED_SUFFIXES
    )


def _append_reddit_rss_suffix(parsed_url: ParseResult) -> str:
    path = parsed_url.path or "/"
    if not path.endswith("/"):
        path = f"{path}/"
    return urlunparse(parsed_url._replace(path=f"{path}.rss"))


def _normalize_reddit_url_for_fetch(url: str) -> str:
    normalized_url = _ensure_url_scheme(url)
    parsed_url = urlparse(normalized_url)

    if parsed_url.netloc.lower() not in REDDIT_HOSTS:
        return normalized_url

    if _is_reddit_structured_url(normalized_url):
        return normalized_url

    return _append_reddit_rss_suffix(parsed_url)


def _tag_text(parent: Tag, tag_name: str) -> str:
    node = parent.find(tag_name, recursive=False)
    if not node:
        return ""
    return unescape(node.get_text(" ", strip=True))


def _link_href(parent: Tag) -> str:
    for link in parent.find_all("link", recursive=False):
        href = link.get("href")
        if href:
            return str(href)
    return ""


def _content_to_markdown(content: str) -> str:
    html_fragment = unescape(content).strip()
    if not html_fragment:
        return ""
    markdown = md(
        html_fragment,
        heading_style="ATX",
        bullets="*",
        convert_images=False,
        strip=["a", "img"],
        autolinks=False,
    )
    return str(markdown).strip()


def _format_reddit_rss_entry(entry: Tag) -> str:
    title = _tag_text(entry, "title") or "Untitled entry"
    author_node = entry.find("author", recursive=False)
    author = _tag_text(author_node, "name") if isinstance(author_node, Tag) else ""
    updated = _tag_text(entry, "updated")
    link = _link_href(entry)
    content_node = entry.find("content", recursive=False) or entry.find("summary", recursive=False)
    content = _content_to_markdown(content_node.decode_contents()) if content_node else ""

    parts = [f"## {title}"]
    metadata = []
    if author:
        metadata.append(f"**Author:** {author}")
    if updated:
        metadata.append(f"**Updated:** {updated}")
    if metadata:
        parts.append(" | ".join(metadata))
    if link:
        parts.append(f"**URL:** <{link}>")
    if content:
        parts.append(content)
    return "\n\n".join(parts)


def _parse_reddit_rss_to_markdown(content: str) -> str | None:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(content, "html.parser")
    feed = soup.find("feed") or soup
    if not isinstance(feed, Tag):
        return None

    title = _tag_text(feed, "title") or "Reddit RSS"
    updated = _tag_text(feed, "updated")
    link = _link_href(feed)
    entries = [entry for entry in feed.find_all("entry", recursive=False) if isinstance(entry, Tag)]

    md_parts = [f"# {title}"]
    if updated:
        md_parts.append(f"**Updated:** {updated}")
    if link:
        md_parts.append(f"**Source:** <{link}>")

    formatted_entries = [_format_reddit_rss_entry(entry) for entry in entries]
    formatted_entries = [entry for entry in formatted_entries if entry.strip()]
    if formatted_entries:
        md_parts.append("\n\n".join(formatted_entries))

    markdown = "\n\n".join(md_parts).strip()
    return markdown or None


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
