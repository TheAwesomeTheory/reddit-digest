"""RSS feed fetcher for Reddit subreddits."""

import feedparser
from dataclasses import dataclass
from datetime import datetime
from html import unescape
import re
from time import mktime

from . import db


@dataclass
class Post:
    """Represents a Reddit post from RSS."""

    post_id: str
    subreddit: str
    title: str
    url: str
    content: str
    author: str
    published: datetime | None = None


def _extract_post_id(entry: dict) -> str:
    """Extract the Reddit post ID from an RSS entry."""
    # The ID is usually in the format 't3_xxxxx'
    entry_id = entry.get("id", "")
    if entry_id.startswith("t3_"):
        return entry_id
    # Fallback: extract from link
    link = entry.get("link", "")
    match = re.search(r"/comments/([a-zA-Z0-9]+)/", link)
    if match:
        return f"t3_{match.group(1)}"
    return entry_id


def _clean_content(entry: dict) -> str:
    """Extract and clean the content from an RSS entry."""
    # Reddit RSS puts content in 'content' or 'summary'
    content = ""
    if "content" in entry and entry["content"]:
        content = entry["content"][0].get("value", "")
    elif "summary" in entry:
        content = entry.get("summary", "")

    # Strip HTML tags and unescape
    content = re.sub(r"<[^>]+>", " ", content)
    content = unescape(content)
    content = re.sub(r"\s+", " ", content).strip()

    # Truncate if too long
    if len(content) > 2000:
        content = content[:2000] + "..."

    return content


def fetch_subreddit(subreddit_config: dict) -> list[Post]:
    """
    Fetch new posts from a subreddit's RSS feed.

    Args:
        subreddit_config: Dict with 'name', 'feed', and 'rules' keys

    Returns:
        List of Post objects that haven't been seen before
    """
    feed_url = subreddit_config["feed"]
    subreddit_name = subreddit_config["name"]

    feed = feedparser.parse(feed_url)

    new_posts = []
    for entry in feed.entries:
        post_id = _extract_post_id(entry)

        # Skip if we've already seen this post
        if db.is_seen(post_id):
            continue

        # Extract published timestamp
        published = None
        if "published_parsed" in entry and entry.published_parsed:
            published = datetime.fromtimestamp(mktime(entry.published_parsed))
        elif "updated_parsed" in entry and entry.updated_parsed:
            published = datetime.fromtimestamp(mktime(entry.updated_parsed))

        post = Post(
            post_id=post_id,
            subreddit=subreddit_name,
            title=entry.get("title", ""),
            url=entry.get("link", ""),
            content=_clean_content(entry),
            author=entry.get("author", "unknown"),
            published=published,
        )

        new_posts.append(post)

    return new_posts


def fetch_all(subreddits: list[dict]) -> list[Post]:
    """
    Fetch new posts from all configured subreddits.

    Args:
        subreddits: List of subreddit configs from config.yaml

    Returns:
        List of all new Post objects across all subreddits
    """
    all_posts = []
    for sub_config in subreddits:
        posts = fetch_subreddit(sub_config)
        all_posts.extend(posts)
    return all_posts
