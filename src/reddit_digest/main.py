"""Main orchestrator for Reddit Digest."""

import logging
import random
import sys
from datetime import datetime, timedelta

from . import config as cfg
from . import db
from . import stats
from .fetcher import fetch_all
from .filter import filter_posts
from .html_generator import generate_html, generate_plain_text
from .emailer import send_email

# Only include posts published within this window
MAX_POST_AGE_MINUTES = 30
# Max posts per digest email
MAX_POSTS_PER_EMAIL = 10

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_digest(dry_run: bool = False) -> None:
    """
    Run a single digest cycle:
    1. Fetch new posts from all subreddits
    2. Filter through Grok
    3. Save approved posts
    4. Generate HTML email
    5. Send email (unless dry_run)
    6. Mark posts as emailed

    Args:
        dry_run: If True, skip sending email and don't mark as emailed.
                 Useful for testing.
    """
    # Start stats tracking
    run_stats = stats.start_run()

    # Load environment and config
    cfg.load_env()
    config = cfg.load_config()
    subreddit_configs = cfg.get_subreddit_configs()

    logger.info(f"Starting digest run...{' (DRY RUN)' if dry_run else ''}")

    # Step 1: Fetch new posts
    subreddits = config.get("subreddits", [])
    if not subreddits:
        logger.warning("No subreddits configured!")
        return

    logger.info(f"Fetching posts from {len(subreddits)} subreddits...")
    run_stats.subreddits_fetched = len(subreddits)
    new_posts = fetch_all(subreddits)
    run_stats.new_posts = len(new_posts)
    logger.info(f"Found {len(new_posts)} new posts")

    # Step 2: Filter new posts through Grok (if any)
    if new_posts:
        logger.info("Filtering posts through Grok...")
        general_rules = config.get("general_rules", "")
        approved = filter_posts(new_posts, general_rules, subreddit_configs)
        run_stats.posts_filtered = len(new_posts)
        run_stats.posts_approved = len(approved)
        run_stats.posts_rejected = len(new_posts) - len(approved)
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
                published_at=post.published,
            )

    # Step 4: Check if we have posts to email (including from previous runs)
    all_unsent = db.get_unsent_approved()
    if not all_unsent:
        logger.info("No posts to email")
        run_stats.finish()
        return

    # Filter to recent posts only (within MAX_POST_AGE_MINUTES)
    cutoff = datetime.now() - timedelta(minutes=MAX_POST_AGE_MINUTES)
    recent_unsent = []
    for p in all_unsent:
        published = p.get("published_at")
        if published:
            # Handle both string and datetime
            if isinstance(published, str):
                try:
                    published = datetime.fromisoformat(published)
                except ValueError:
                    continue
            if published >= cutoff:
                recent_unsent.append(p)

    run_stats.recent_posts_available = len(recent_unsent)
    run_stats.old_posts_skipped = len(all_unsent) - len(recent_unsent)

    if not recent_unsent:
        logger.info(f"No recent posts (within {MAX_POST_AGE_MINUTES} min) to email")
        # Mark old posts as emailed so they don't pile up
        post_ids = [p["id"] for p in all_unsent]
        if not dry_run and post_ids:
            db.mark_emailed(post_ids)
            logger.info(f"Marked {len(post_ids)} old posts as emailed (skipped)")
        run_stats.finish()
        return

    # Shuffle and limit to MAX_POSTS_PER_EMAIL
    random.shuffle(recent_unsent)
    unsent = recent_unsent[:MAX_POSTS_PER_EMAIL]
    run_stats.posts_in_email = len(unsent)

    logger.info(f"Generating email for {len(unsent)} posts (of {len(recent_unsent)} recent, {len(all_unsent)} total)...")

    # Step 5: Generate HTML email
    html = generate_html(unsent)
    plain = generate_plain_text(unsent)

    # Get recipients for stats
    from .emailer import _get_recipients_from_config
    run_stats.recipients = _get_recipients_from_config()

    # Step 6: Send email (unless dry run)
    if dry_run:
        run_stats.finish()
        logger.info("DRY RUN: Would send email with the following content:")
        logger.info(f"HTML length: {len(html)} characters")
        logger.info(f"Posts included: {[p['title'][:50] for p in unsent]}")
        logger.info("DRY RUN: Skipping email send and not marking as emailed")
        # Log debug summary even in dry run
        logger.info(f"\n{run_stats.generate_summary()}")
        return

    logger.info("Sending email...")
    try:
        # Finish stats and generate summary for attachment
        run_stats.finish()
        debug_summary = run_stats.generate_summary()

        send_email(html, plain, debug_summary=debug_summary)
        run_stats.email_sent = True
        logger.info("Email sent successfully!")

        # Step 7: Mark ALL unsent posts as emailed (including ones we filtered/skipped)
        all_post_ids = [p["id"] for p in all_unsent]
        db.mark_emailed(all_post_ids)
        logger.info(f"Marked {len(all_post_ids)} posts as emailed")

        # Log the debug summary
        logger.info(f"Total API cost: ${run_stats.total_cost:.4f}")

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
