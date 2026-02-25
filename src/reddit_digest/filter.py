"""Grok-based content filtering for Reddit posts."""

import os
import re
from dataclasses import dataclass
from openai import OpenAI

from .fetcher import Post


@dataclass
class FilterResult:
    """Result of filtering a post through Grok."""

    approved: bool
    reason: str


def get_client() -> OpenAI:
    """Get an OpenAI client configured for xAI."""
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise ValueError("XAI_API_KEY environment variable not set")

    return OpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1",
    )


def filter_post(
    post: Post,
    general_rules: str,
    subreddit_rules: str,
) -> FilterResult:
    """
    Filter a post using Grok to decide if it should be included.

    Args:
        post: The Post to evaluate
        general_rules: General filtering rules from config
        subreddit_rules: Subreddit-specific rules from config

    Returns:
        FilterResult with approved status and reason
    """
    client = get_client()

    prompt = f"""You are a content curator. Evaluate this Reddit post and decide if it should be included in a personal digest.

GENERAL RULES:
{general_rules}

SUBREDDIT-SPECIFIC RULES (r/{post.subreddit}):
{subreddit_rules}

POST:
Title: {post.title}
Author: u/{post.author}
Content: {post.content}
URL: {post.url}

Respond with EXACTLY one of these formats:
APPROVE: <one sentence explaining why this is valuable>
or
REJECT: <one sentence explaining why>"""

    response = client.chat.completions.create(
        model="grok-3-fast-latest",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.3,
    )

    result_text = response.choices[0].message.content.strip()

    # Parse the response
    if result_text.upper().startswith("APPROVE:"):
        reason = result_text[8:].strip()
        return FilterResult(approved=True, reason=reason)
    elif result_text.upper().startswith("REJECT:"):
        reason = result_text[7:].strip()
        return FilterResult(approved=False, reason=reason)
    else:
        # If response doesn't follow format, be conservative and reject
        return FilterResult(approved=False, reason=f"Unclear response: {result_text[:100]}")


def filter_posts(
    posts: list[Post],
    general_rules: str,
    subreddit_configs: dict[str, dict],
) -> list[tuple[Post, FilterResult]]:
    """
    Filter multiple posts through Grok.

    Args:
        posts: List of posts to filter
        general_rules: General filtering rules
        subreddit_configs: Dict mapping subreddit name to config (including rules)

    Returns:
        List of (Post, FilterResult) tuples for approved posts only
    """
    approved = []

    for post in posts:
        sub_config = subreddit_configs.get(post.subreddit, {})
        sub_rules = sub_config.get("rules", "No specific rules.")

        result = filter_post(post, general_rules, sub_rules)

        if result.approved:
            approved.append((post, result))

    return approved
