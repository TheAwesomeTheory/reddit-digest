"""Main orchestrator for Reddit Digest."""

import logging
import sys

from . import config as cfg
from . import db
from .fetcher import fetch_all
from .filter import filter_posts
from .html_generator import generate_html, generate_plain_text
from .emailer import send_email

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_digest() -> None:
    """
    Run a single digest cycle:
    1. Fetch new posts from all subreddits
    2. Filter through Grok
    3. Save approved posts
    4. Generate HTML email
    5. Send email
    6. Mark posts as emailed
    """
    # Load environment and config
    cfg.load_env()
    config = cfg.load_config()
    subreddit_configs = cfg.get_subreddit_configs()

    logger.info("Starting digest run...")

    # Step 1: Fetch new posts
    subreddits = config.get("subreddits", [])
    if not subreddits:
        logger.warning("No subreddits configured!")
        return

    logger.info(f"Fetching posts from {len(subreddits)} subreddits...")
    new_posts = fetch_all(subreddits)
    logger.info(f"Found {len(new_posts)} new posts")

    if not new_posts:
        logger.info("No new posts to process")
        return

    # Step 2: Filter through Grok
    logger.info("Filtering posts through Grok...")
    general_rules = config.get("general_rules", "")
    approved = filter_posts(new_posts, general_rules, subreddit_configs)
    logger.info(f"Grok approved {len(approved)} of {len(new_posts)} posts")

    # Step 3: Mark all posts as seen and save approved ones
    for post in new_posts:
        db.mark_seen(post.post_id, post.subreddit, post.title, post.url)

    for post, result in approved:
        db.save_approved(
            post_id=post.post_id,
            subreddit=post.subreddit,
            title=post.title,
            url=post.url,
            content=post.content,
            grok_reason=result.reason,
        )

    # Step 4: Check if we have posts to email
    unsent = db.get_unsent_approved()
    if not unsent:
        logger.info("No posts to email")
        return

    logger.info(f"Generating email for {len(unsent)} posts...")

    # Step 5: Generate HTML email
    html = generate_html(unsent)
    plain = generate_plain_text(unsent)

    # Step 6: Send email
    logger.info("Sending email...")
    try:
        send_email(html, plain)
        logger.info("Email sent successfully!")

        # Step 7: Mark as emailed
        post_ids = [p["id"] for p in unsent]
        db.mark_emailed(post_ids)
        logger.info(f"Marked {len(post_ids)} posts as emailed")

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise


def main() -> None:
    """Entry point for the reddit-digest command."""
    try:
        run_digest()
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
