# Reddit Digest

AI-curated Reddit feed that emails you filtered posts every 30 minutes.

## Quick Commands

```bash
uv run rd run                    # Run manually
uv run rd service health         # Check if service is healthy
uv run rd service status         # Detailed systemd status
uv run rd service recent-logs -n 20  # View recent logs
```

## First-Time Setup

```bash
# 1. Set API keys
uv run rd config set-key xai      # xAI API key for Grok
uv run rd config set-key gmail    # Gmail app password

# 2. Edit config.yaml with your email and subreddits

# 3. Install systemd service
uv run rd service install

# 4. Start the service
uv run rd service start

# 5. (Optional) Enable on boot
systemctl --user enable reddit-digest.timer
```

## For Agents: Monitoring & Health

### Check Health (returns exit code 0 if healthy)

```bash
uv run rd service health
```

This checks:
- Is the timer active?
- Is the service in a failed state?
- Has it run in the last 2 hours?
- Are unsent posts piling up?

### View Recent Logs (non-streaming, safe for agents)

```bash
uv run rd service recent-logs -n 50
```

### Database Stats

```bash
uv run rd db stats
```

Shows: posts seen, posts approved, pending emails, last fetch/email times.

## For Agents: Deploying Changes

### After Making Code Changes

```bash
# 1. Test the change works
uv run rd deploy test-run

# 2. If successful, restart service
uv run rd service restart

# 3. Verify health
uv run rd service health
```

### If Something Breaks

```bash
# 1. Check what went wrong
uv run rd service recent-logs -n 50

# 2. See deployment history
uv run rd deploy history

# 3. Rollback to a known good commit
uv run rd deploy rollback <commit-hash>

# 4. Verify health
uv run rd service health
```

### Rollback Workflow

```bash
# See recent commits
uv run rd deploy history -n 10

# Output:
# a1b2c3d Fix email formatting
# e4f5g6h Add new subreddit
# i7j8k9l Initial commit

# Rollback to a specific commit
uv run rd deploy rollback e4f5g6h

# This will:
# 1. Stop the service
# 2. Checkout that commit
# 3. Reinstall dependencies (uv sync)
# 4. Restart the service
```

## Configuration

### Config File: `config.yaml`

```yaml
email:
  sender: you@gmail.com
  recipient: you@gmail.com

general_rules: |
  Only approve educational, insightful posts.
  Reject rage-bait and low-effort content.

subreddits:
  - name: programming
    feed: https://www.reddit.com/r/programming/new/.rss
    rules: |
      Prioritize: technical deep-dives, tool releases
      Reject: career advice, language debates
```

### Add a Subreddit

```bash
uv run rd config add-subreddit
```

### Update Rules for a Subreddit

```bash
echo "New rules here" | uv run rd rules set programming
```

## Environment Variables

Stored in `.env`:
- `XAI_API_KEY` - Grok API key from x.ai
- `GMAIL_APP_PASSWORD` - Gmail app password

## Service Management

```bash
uv run rd service install     # Install systemd files
uv run rd service uninstall   # Remove systemd files
uv run rd service start       # Start timer
uv run rd service stop        # Stop timer
uv run rd service restart     # Restart timer
uv run rd service status      # Show systemd status
uv run rd service health      # Quick health check (exit code)
uv run rd service logs        # Stream logs (interactive)
uv run rd service recent-logs # Show recent logs (non-interactive)
```

## File Locations

| File | Purpose |
|------|---------|
| `config.yaml` | Subreddits and filtering rules |
| `.env` | API keys (gitignored) |
| `digest.db` | SQLite database |
| `systemd/` | Service and timer templates |

## Architecture

```
Timer (30 min) → RSS Fetch → Grok Filter → SQLite → Grok HTML → Gmail
```

1. **Fetch**: Get new posts from subreddit RSS feeds
2. **Filter**: Grok evaluates each post against your rules
3. **Store**: Approved posts saved to SQLite
4. **Generate**: Grok creates a uniquely styled HTML email
5. **Send**: Email via Gmail SMTP
6. **Track**: Mark posts as emailed

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No emails | `uv run rd service recent-logs -n 50` |
| Test email works? | `uv run rd test-email` |
| Service failing | `uv run rd service health` |
| Need to reprocess | `uv run rd db clear-seen` |
| Bad deploy | `uv run rd deploy rollback <commit>` |
