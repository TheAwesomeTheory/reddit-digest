"""Configuration loading and management."""

import os
from pathlib import Path
import yaml

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


def load_config() -> dict:
    """Load configuration from config.yaml."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    """Save configuration to config.yaml."""
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def get_subreddit_configs() -> dict[str, dict]:
    """Get a dict mapping subreddit names to their configs."""
    config = load_config()
    return {sub["name"]: sub for sub in config.get("subreddits", [])}


def add_subreddit(name: str, feed: str, rules: str) -> None:
    """Add a new subreddit to the config."""
    config = load_config()

    if "subreddits" not in config:
        config["subreddits"] = []

    # Check if already exists
    for sub in config["subreddits"]:
        if sub["name"] == name:
            raise ValueError(f"Subreddit {name} already exists in config")

    config["subreddits"].append({
        "name": name,
        "feed": feed,
        "rules": rules,
    })

    save_config(config)


def update_subreddit_rules(name: str, rules: str) -> None:
    """Update rules for a subreddit."""
    config = load_config()

    for sub in config.get("subreddits", []):
        if sub["name"] == name:
            sub["rules"] = rules
            save_config(config)
            return

    raise ValueError(f"Subreddit {name} not found in config")


def load_env() -> None:
    """Load environment variables from .env file if it exists."""
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
