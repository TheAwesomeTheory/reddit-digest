"""Track API usage and costs for Reddit Digest runs."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# Pricing per million tokens (as of Feb 2025)
PRICING = {
    "grok-4-fast-reasoning": {"input": 0.20, "output": 0.50},
    "grok-4-1-fast-reasoning": {"input": 0.20, "output": 0.50},
    "grok-code-fast-1": {"input": 0.20, "output": 1.50},
    "grok-3-mini": {"input": 0.30, "output": 0.50},
    "grok-3": {"input": 3.00, "output": 15.00},
    "grok-4-0709": {"input": 3.00, "output": 15.00},
}


@dataclass
class APICall:
    """Record of a single API call."""

    model: str
    purpose: str  # "filter" or "html"
    input_tokens: int
    output_tokens: int
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def cost(self) -> float:
        """Calculate cost in USD."""
        pricing = PRICING.get(self.model, {"input": 1.0, "output": 1.0})
        input_cost = (self.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


@dataclass
class RunStats:
    """Statistics for a single digest run."""

    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    # Fetch stats
    subreddits_fetched: int = 0
    posts_fetched: int = 0
    new_posts: int = 0

    # Filter stats
    posts_filtered: int = 0
    posts_approved: int = 0
    posts_rejected: int = 0

    # Email stats
    posts_in_email: int = 0
    recent_posts_available: int = 0
    old_posts_skipped: int = 0
    recipients: list[str] = field(default_factory=list)
    email_sent: bool = False

    # API calls
    api_calls: list[APICall] = field(default_factory=list)

    def add_api_call(
        self,
        model: str,
        purpose: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record an API call."""
        self.api_calls.append(
            APICall(
                model=model,
                purpose=purpose,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        )

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.api_calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.api_calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost(self) -> float:
        return sum(c.cost for c in self.api_calls)

    @property
    def filter_calls(self) -> list[APICall]:
        return [c for c in self.api_calls if c.purpose == "filter"]

    @property
    def html_calls(self) -> list[APICall]:
        return [c for c in self.api_calls if c.purpose == "html"]

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()

    def finish(self) -> None:
        """Mark the run as complete."""
        self.end_time = datetime.now()

    def generate_summary(self) -> str:
        """Generate a human-readable debug summary."""
        lines = [
            "=" * 60,
            "REDDIT DIGEST - RUN SUMMARY",
            "=" * 60,
            "",
            f"Run Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {self.duration_seconds:.1f} seconds",
            "",
            "-" * 40,
            "FETCH STATS",
            "-" * 40,
            f"Subreddits checked: {self.subreddits_fetched}",
            f"New posts found: {self.new_posts}",
            "",
            "-" * 40,
            "FILTER STATS",
            "-" * 40,
            f"Posts filtered: {self.posts_filtered}",
            f"Posts approved: {self.posts_approved}",
            f"Posts rejected: {self.posts_rejected}",
            f"Approval rate: {(self.posts_approved / self.posts_filtered * 100) if self.posts_filtered else 0:.1f}%",
            "",
            "-" * 40,
            "EMAIL STATS",
            "-" * 40,
            f"Recent posts available: {self.recent_posts_available}",
            f"Old posts skipped: {self.old_posts_skipped}",
            f"Posts in email: {self.posts_in_email}",
            f"Recipients: {', '.join(self.recipients) if self.recipients else 'N/A'}",
            f"Email sent: {'Yes' if self.email_sent else 'No'}",
            "",
            "-" * 40,
            "API USAGE",
            "-" * 40,
        ]

        # Filter API calls
        filter_calls = self.filter_calls
        if filter_calls:
            filter_input = sum(c.input_tokens for c in filter_calls)
            filter_output = sum(c.output_tokens for c in filter_calls)
            filter_cost = sum(c.cost for c in filter_calls)
            lines.extend([
                f"Filter calls: {len(filter_calls)}",
                f"  Model: {filter_calls[0].model if filter_calls else 'N/A'}",
                f"  Input tokens: {filter_input:,}",
                f"  Output tokens: {filter_output:,}",
                f"  Cost: ${filter_cost:.4f}",
                "",
            ])

        # HTML API calls
        html_calls = self.html_calls
        if html_calls:
            html_input = sum(c.input_tokens for c in html_calls)
            html_output = sum(c.output_tokens for c in html_calls)
            html_cost = sum(c.cost for c in html_calls)
            lines.extend([
                f"HTML generation calls: {len(html_calls)}",
                f"  Model: {html_calls[0].model if html_calls else 'N/A'}",
                f"  Input tokens: {html_input:,}",
                f"  Output tokens: {html_output:,}",
                f"  Cost: ${html_cost:.4f}",
                "",
            ])

        # Totals
        lines.extend([
            "-" * 40,
            "TOTAL COST",
            "-" * 40,
            f"Total API calls: {len(self.api_calls)}",
            f"Total input tokens: {self.total_input_tokens:,}",
            f"Total output tokens: {self.total_output_tokens:,}",
            f"Total tokens: {self.total_tokens:,}",
            f"TOTAL COST: ${self.total_cost:.4f}",
            "",
            "=" * 60,
        ])

        return "\n".join(lines)


# Global stats instance for the current run
_current_stats: Optional[RunStats] = None


def start_run() -> RunStats:
    """Start a new run and return the stats object."""
    global _current_stats
    _current_stats = RunStats()
    return _current_stats


def get_current_stats() -> Optional[RunStats]:
    """Get the current run stats."""
    return _current_stats


def reset_stats() -> None:
    """Reset the current stats."""
    global _current_stats
    _current_stats = None
