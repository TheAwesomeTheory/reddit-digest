"""CLI commands for managing Reddit Digest."""

import os
import subprocess
import sys
from pathlib import Path

import click

from . import config as cfg


@click.group()
def cli():
    """Reddit Digest - AI-curated Reddit feed."""
    cfg.load_env()


@cli.command()
def run():
    """Run the digest manually (fetch, filter, email)."""
    from .main import run_digest
    run_digest()


# --- Service management ---


@cli.group()
def service():
    """Manage the systemd service."""
    pass


@service.command()
def status():
    """Show service status."""
    subprocess.run(["systemctl", "--user", "status", "reddit-digest.timer"], check=False)


@service.command()
def start():
    """Start the service."""
    subprocess.run(["systemctl", "--user", "start", "reddit-digest.timer"], check=True)
    click.echo("Service started.")


@service.command()
def stop():
    """Stop the service."""
    subprocess.run(["systemctl", "--user", "stop", "reddit-digest.timer"], check=True)
    click.echo("Service stopped.")


@service.command()
def restart():
    """Restart the service."""
    subprocess.run(["systemctl", "--user", "restart", "reddit-digest.timer"], check=True)
    click.echo("Service restarted.")


@service.command()
def logs():
    """View service logs."""
    subprocess.run(
        ["journalctl", "--user", "-u", "reddit-digest.service", "-f"],
        check=False,
    )


@service.command("recent-logs")
@click.option("-n", "--lines", default=50, help="Number of lines to show")
def recent_logs(lines: int):
    """Show recent logs (non-streaming, for agents)."""
    result = subprocess.run(
        ["journalctl", "--user", "-u", "reddit-digest.service", "-n", str(lines), "--no-pager"],
        capture_output=True,
        text=True,
    )
    click.echo(result.stdout)
    if result.stderr:
        click.echo(result.stderr, err=True)


@service.command()
def install():
    """Install systemd service and timer files."""
    systemd_dir = Path(__file__).parent.parent.parent / "systemd"
    user_systemd = Path.home() / ".config" / "systemd" / "user"
    project_dir = Path(__file__).parent.parent.parent.resolve()

    # Create user systemd directory if needed
    user_systemd.mkdir(parents=True, exist_ok=True)

    # Read and customize service file
    service_src = systemd_dir / "reddit-digest.service"
    service_content = service_src.read_text()
    # Replace %h with actual paths for clarity
    service_content = service_content.replace(
        "WorkingDirectory=%h/reddit-digest",
        f"WorkingDirectory={project_dir}"
    )

    # Write service file
    service_dst = user_systemd / "reddit-digest.service"
    service_dst.write_text(service_content)
    click.echo(f"Installed: {service_dst}")

    # Copy timer file
    timer_src = systemd_dir / "reddit-digest.timer"
    timer_dst = user_systemd / "reddit-digest.timer"
    timer_dst.write_text(timer_src.read_text())
    click.echo(f"Installed: {timer_dst}")

    # Reload systemd
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    click.echo("Reloaded systemd daemon")

    click.echo("\nTo start the service:")
    click.echo("  uv run rd service start")
    click.echo("\nTo enable on boot:")
    click.echo("  systemctl --user enable reddit-digest.timer")


@service.command()
def uninstall():
    """Remove systemd service and timer files."""
    user_systemd = Path.home() / ".config" / "systemd" / "user"

    # Stop if running
    subprocess.run(["systemctl", "--user", "stop", "reddit-digest.timer"], check=False)
    subprocess.run(["systemctl", "--user", "disable", "reddit-digest.timer"], check=False)

    # Remove files
    for filename in ["reddit-digest.service", "reddit-digest.timer"]:
        filepath = user_systemd / filename
        if filepath.exists():
            filepath.unlink()
            click.echo(f"Removed: {filepath}")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    click.echo("Service uninstalled.")


@service.command()
def health():
    """Check service health (for agents). Exit code 0 = healthy."""
    from . import db as database

    issues = []

    # Check 1: Is timer active?
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "reddit-digest.timer"],
        capture_output=True,
        text=True,
    )
    timer_active = result.stdout.strip() == "active"
    if not timer_active:
        issues.append("Timer is not active")

    # Check 2: Recent failures?
    result = subprocess.run(
        ["systemctl", "--user", "is-failed", "reddit-digest.service"],
        capture_output=True,
        text=True,
    )
    service_failed = result.stdout.strip() == "failed"
    if service_failed:
        issues.append("Service is in failed state")

    # Check 3: Has it run recently? (within last 2 hours)
    stats = database.get_stats()
    if stats["last_fetch"]:
        from datetime import datetime, timedelta
        last_fetch = datetime.fromisoformat(stats["last_fetch"])
        if datetime.now() - last_fetch > timedelta(hours=2):
            issues.append(f"No fetch in last 2 hours (last: {stats['last_fetch']})")

    # Check 4: Any unsent posts piling up?
    if stats["unsent_posts"] > 20:
        issues.append(f"Too many unsent posts ({stats['unsent_posts']}) - email may be failing")

    # Report
    if issues:
        click.secho("UNHEALTHY", fg="red", bold=True)
        for issue in issues:
            click.echo(f"  - {issue}")
        sys.exit(1)
    else:
        click.secho("HEALTHY", fg="green", bold=True)
        click.echo(f"  Timer: {'active' if timer_active else 'inactive'}")
        click.echo(f"  Last fetch: {stats['last_fetch'] or 'Never'}")
        click.echo(f"  Last email: {stats['last_email'] or 'Never'}")
        click.echo(f"  Pending posts: {stats['unsent_posts']}")
        sys.exit(0)


# --- Config management ---


@cli.group("config")
def config_group():
    """Manage configuration."""
    pass


@config_group.command("show")
def config_show():
    """Show current configuration."""
    config = cfg.load_config()

    click.echo("\n=== Email Settings ===")
    email = config.get("email", {})
    click.echo(f"Sender: {email.get('sender', 'NOT SET')}")
    click.echo(f"Recipient: {email.get('recipient', 'NOT SET')}")

    click.echo("\n=== General Rules ===")
    click.echo(config.get("general_rules", "NOT SET"))

    click.echo("\n=== Subreddits ===")
    for sub in config.get("subreddits", []):
        click.echo(f"\n[r/{sub['name']}]")
        click.echo(f"  Feed: {sub['feed']}")
        click.echo(f"  Rules: {sub.get('rules', 'None')[:100]}...")


@config_group.command("set-key")
@click.argument("key_type", type=click.Choice(["xai", "gmail"]))
def config_set_key(key_type: str):
    """Set an API key (xai or gmail)."""
    env_path = Path(__file__).parent.parent.parent / ".env"

    # Read existing .env
    env_vars = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k] = v

    # Get the new key
    if key_type == "xai":
        var_name = "XAI_API_KEY"
        prompt = "Enter your xAI API key"
    else:
        var_name = "GMAIL_APP_PASSWORD"
        prompt = "Enter your Gmail app password"

    value = click.prompt(prompt, hide_input=True)
    env_vars[var_name] = value

    # Write back
    with open(env_path, "w") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")

    click.echo(f"{var_name} saved to .env")


@config_group.command("add-subreddit")
def config_add_subreddit():
    """Add a new subreddit to monitor."""
    name = click.prompt("Subreddit name (without r/)")
    feed = f"https://www.reddit.com/r/{name}/new/.rss"

    click.echo(f"Feed URL will be: {feed}")
    if not click.confirm("Is this correct?"):
        feed = click.prompt("Enter custom feed URL")

    click.echo("\nEnter filtering rules for this subreddit.")
    click.echo("(Describe what to prioritize and what to reject)")
    rules = click.prompt("Rules")

    cfg.add_subreddit(name, feed, rules)
    click.echo(f"\nAdded r/{name} to config.yaml")


@config_group.command("edit")
def config_edit():
    """Open config.yaml in $EDITOR."""
    editor = os.environ.get("EDITOR", "nano")
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    subprocess.run([editor, str(config_path)])


# --- Rules management ---


@cli.group()
def rules():
    """Manage subreddit filtering rules."""
    pass


@rules.command("show")
@click.argument("subreddit")
def rules_show(subreddit: str):
    """Show rules for a subreddit."""
    configs = cfg.get_subreddit_configs()
    if subreddit not in configs:
        click.echo(f"Subreddit r/{subreddit} not found in config", err=True)
        sys.exit(1)

    click.echo(f"\n=== Rules for r/{subreddit} ===\n")
    click.echo(configs[subreddit].get("rules", "No specific rules set."))


@rules.command("set")
@click.argument("subreddit")
def rules_set(subreddit: str):
    """Set rules for a subreddit (reads from stdin)."""
    click.echo("Enter new rules (Ctrl+D when done):")
    rules_text = sys.stdin.read().strip()

    cfg.update_subreddit_rules(subreddit, rules_text)
    click.echo(f"\nUpdated rules for r/{subreddit}")


# --- Database commands ---


@cli.group()
def db():
    """Database operations."""
    pass


@db.command("stats")
def db_stats():
    """Show database statistics."""
    from . import db as database

    stats = database.get_stats()

    click.echo("\n=== Database Stats ===")
    click.echo(f"Total posts seen: {stats['seen_posts']}")
    click.echo(f"Total posts approved: {stats['approved_posts']}")
    click.echo(f"Posts pending email: {stats['unsent_posts']}")
    click.echo(f"Last fetch: {stats['last_fetch'] or 'Never'}")
    click.echo(f"Last email sent: {stats['last_email'] or 'Never'}")


@db.command("clear-seen")
def db_clear_seen():
    """Clear seen posts history (allows re-processing)."""
    if not click.confirm("This will allow all posts to be re-processed. Continue?"):
        return

    from . import db as database

    count = database.clear_seen()
    click.echo(f"Cleared {count} seen posts.")


# --- Testing commands ---


@cli.command("test-email")
def test_email():
    """Send a test email to verify configuration."""
    from .emailer import send_test_email

    click.echo("Sending test email...")
    try:
        send_test_email()
        click.echo("Test email sent successfully!")
    except Exception as e:
        click.echo(f"Failed to send test email: {e}", err=True)
        sys.exit(1)


@cli.command("test-filter")
@click.argument("url")
def test_filter(url: str):
    """Test filtering on a specific Reddit post URL."""
    import re
    import feedparser
    from .filter import filter_post
    from .fetcher import Post, _clean_content, _extract_post_id

    # Extract subreddit from URL
    match = re.search(r"reddit\.com/r/([^/]+)/", url)
    if not match:
        click.echo("Could not parse subreddit from URL", err=True)
        sys.exit(1)

    subreddit = match.group(1)

    # Try to fetch the post via RSS
    click.echo(f"Fetching post from r/{subreddit}...")

    # Get the JSON version of the post
    json_url = url.rstrip("/") + ".json"
    click.echo(f"(Note: Using RSS feed to find post)")

    # Load config
    config = cfg.load_config()
    sub_configs = cfg.get_subreddit_configs()
    sub_rules = sub_configs.get(subreddit, {}).get("rules", "No specific rules.")

    # Create a mock post for testing
    click.echo("\nEnter post title:")
    title = input().strip()
    click.echo("Enter post content (or press Enter for none):")
    content = input().strip()

    post = Post(
        post_id="test",
        subreddit=subreddit,
        title=title,
        url=url,
        content=content,
        author="test",
    )

    click.echo("\n=== Filtering ===")
    click.echo(f"General rules: {config.get('general_rules', 'None')[:100]}...")
    click.echo(f"Subreddit rules: {sub_rules[:100]}...")

    result = filter_post(post, config.get("general_rules", ""), sub_rules)

    click.echo("\n=== Result ===")
    if result.approved:
        click.secho("APPROVED", fg="green", bold=True)
    else:
        click.secho("REJECTED", fg="red", bold=True)
    click.echo(f"Reason: {result.reason}")


# --- Deployment/versioning commands ---


@cli.group()
def deploy():
    """Deployment and version management (for agents)."""
    pass


@deploy.command("current")
def deploy_current():
    """Show current deployed version (git commit)."""
    project_dir = Path(__file__).parent.parent.parent
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        commit = result.stdout.strip()
        # Get commit message
        msg_result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        msg = msg_result.stdout.strip() if msg_result.returncode == 0 else ""
        click.echo(f"Current version: {commit}")
        click.echo(f"Commit message: {msg}")
    else:
        click.echo("Not a git repository or git not available", err=True)
        sys.exit(1)


@deploy.command("history")
@click.option("-n", "--count", default=10, help="Number of commits to show")
def deploy_history(count: int):
    """Show recent deployment history (git log)."""
    project_dir = Path(__file__).parent.parent.parent
    subprocess.run(
        ["git", "log", f"-{count}", "--oneline"],
        cwd=project_dir,
    )


@deploy.command("rollback")
@click.argument("commit")
@click.option("--force", is_flag=True, help="Skip confirmation")
def deploy_rollback(commit: str, force: bool):
    """Rollback to a specific commit."""
    project_dir = Path(__file__).parent.parent.parent

    # Show what we're rolling back to
    result = subprocess.run(
        ["git", "log", "-1", "--format=%h %s", commit],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        click.echo(f"Commit {commit} not found", err=True)
        sys.exit(1)

    click.echo(f"Rolling back to: {result.stdout.strip()}")

    if not force and not click.confirm("Proceed with rollback?"):
        return

    # Stop service
    click.echo("Stopping service...")
    subprocess.run(["systemctl", "--user", "stop", "reddit-digest.timer"], check=False)

    # Checkout the commit
    click.echo(f"Checking out {commit}...")
    result = subprocess.run(
        ["git", "checkout", commit],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        click.echo(f"Rollback failed: {result.stderr}", err=True)
        sys.exit(1)

    # Reinstall dependencies
    click.echo("Reinstalling dependencies...")
    subprocess.run(["uv", "sync"], cwd=project_dir, check=True)

    # Restart service
    click.echo("Starting service...")
    subprocess.run(["systemctl", "--user", "start", "reddit-digest.timer"], check=True)

    click.secho("Rollback complete!", fg="green")


@deploy.command("test-run")
def deploy_test_run():
    """Run a test cycle and report success/failure (for CI/agents)."""
    from .main import run_digest

    click.echo("Running test digest cycle...")
    try:
        run_digest()
        click.secho("SUCCESS: Digest cycle completed", fg="green")
        sys.exit(0)
    except Exception as e:
        click.secho(f"FAILURE: {e}", fg="red", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
