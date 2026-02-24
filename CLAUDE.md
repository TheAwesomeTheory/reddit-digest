# Reddit Digest

AI-curated Reddit feed that emails filtered posts every 30 minutes.

## Quick Reference

```bash
uv run rd run                    # Run digest manually
uv run rd service health         # Check health (exit 0 = good)
uv run rd service recent-logs -n 50  # View logs
uv run rd db stats               # See post counts
```

---

## Development Workflow

### Making Code Changes

**Always follow this workflow:**

```bash
# 1. Make your code changes

# 2. Test locally (dry run - no email sent, validates code works)
uv run rd deploy test-run

# 3. If test passes, commit
git add -A
git commit -m "Description of change"

# 4. If service is running, restart it
uv run rd service restart

# 5. Verify it's healthy
uv run rd service health
```

**Note:** `deploy test-run` uses dry-run mode by default - it won't send emails or mark posts as emailed. To test with real email: `uv run rd deploy test-run --send-email`

### Making Config Changes (config.yaml)

Config changes don't need a test-run, just restart:

```bash
# 1. Edit config.yaml

# 2. Restart service to pick up changes
uv run rd service restart

# 3. Verify
uv run rd service health
```

### Adding a New Subreddit

```bash
# Option 1: Interactive
uv run rd config add-subreddit

# Option 2: Edit config.yaml directly
# Add to the subreddits list:
#   - name: newsubreddit
#     feed: https://www.reddit.com/r/newsubreddit/new/.rss
#     rules: |
#       Prioritize: ...
#       Reject: ...

# Then restart
uv run rd service restart
```

### Modifying Filtering Rules

```bash
# View current rules
uv run rd rules show programming

# Update rules (via stdin)
echo "Prioritize: technical posts
Reject: memes and career advice" | uv run rd rules set programming

# Or edit config.yaml directly, then:
uv run rd service restart
```

---

## Deployment

### First-Time Setup on a New Server

```bash
# 1. Clone the repo
git clone <repo-url> ~/reddit-digest
cd ~/reddit-digest

# 2. Install dependencies
uv sync

# 3. Set up API keys
uv run rd config set-key xai      # Enter your xAI API key
uv run rd config set-key gmail    # Enter Gmail app password

# 4. Configure email addresses in config.yaml
#    Set sender: and recipient: to your email

# 5. Test email works
uv run rd test-email

# 6. Test a full run
uv run rd run

# 7. Install systemd service
uv run rd service install

# 8. Start the service
uv run rd service start

# 9. Enable on boot (optional)
systemctl --user enable reddit-digest.timer

# 10. Verify
uv run rd service health
```

### Deploying Code Updates

```bash
# 1. Pull latest code
git pull

# 2. Update dependencies (in case they changed)
uv sync

# 3. Test the changes work
uv run rd deploy test-run

# 4. Restart service
uv run rd service restart

# 5. Verify healthy
uv run rd service health

# 6. Watch logs for a bit to confirm
uv run rd service recent-logs -n 20
```

---

## Troubleshooting

### Service Not Running

```bash
# Check status
uv run rd service health

# If timer not active:
uv run rd service start

# If service failed:
uv run rd service recent-logs -n 50
# Read the error, fix the issue, then:
uv run rd service restart
```

### No Emails Being Sent

```bash
# 1. Check if service is running
uv run rd service health

# 2. Check for errors in logs
uv run rd service recent-logs -n 50

# 3. Check database - are posts being fetched?
uv run rd db stats

# If "Posts pending email" > 0, email sending is failing
# If "Total posts seen" = 0, RSS fetching is failing

# 4. Test email independently
uv run rd test-email

# 5. If test-email fails, check:
#    - Is GMAIL_APP_PASSWORD set correctly in .env?
#    - Is the Gmail account configured for app passwords?
```

### Posts Not Being Approved

```bash
# 1. Check if posts are being fetched
uv run rd db stats
# "Total posts seen" should be > 0

# 2. If posts are seen but none approved, your rules may be too strict
# Review rules:
uv run rd config show

# 3. Test filtering on a specific post
uv run rd test-filter https://reddit.com/r/programming/comments/xxx
```

### Something Broke After a Code Change

```bash
# 1. Check what went wrong
uv run rd service recent-logs -n 50

# 2. See recent commits
uv run rd deploy history

# 3. Identify the last known good commit

# 4. Rollback
uv run rd deploy rollback <commit-hash>

# 5. Verify fixed
uv run rd service health
```

### Need to Reprocess All Posts

```bash
# Clear the "seen" history - posts will be re-fetched and re-filtered
uv run rd db clear-seen

# Run manually to process them now
uv run rd run
```

---

## File Reference

| File | Purpose | When to Edit |
|------|---------|--------------|
| `config.yaml` | Subreddits, rules, email settings | Adding subs, changing rules |
| `.env` | API keys (XAI_API_KEY, GMAIL_APP_PASSWORD) | Rotating keys |
| `src/reddit_digest/*.py` | Application code | Adding features, fixing bugs |
| `systemd/*.service` | Systemd unit files | Changing how service runs |
| `digest.db` | SQLite database | Don't edit directly |

### Key Source Files

| File | Purpose |
|------|---------|
| `main.py` | Orchestrates the full digest cycle |
| `fetcher.py` | Fetches posts from RSS feeds |
| `filter.py` | Sends posts to Grok for filtering |
| `html_generator.py` | Grok generates styled HTML |
| `emailer.py` | Sends email via Gmail SMTP |
| `db.py` | SQLite operations |
| `cli.py` | All CLI commands |
| `config.py` | Config loading/saving |

---

## CLI Command Reference

### Core Commands
```bash
uv run rd run              # Run digest cycle (sends email)
uv run rd run --dry-run    # Run without sending email
uv run rd test-email       # Send test email
uv run rd test-filter URL  # Test filtering on a post
```

### Service Management
```bash
uv run rd service status      # Detailed systemd status
uv run rd service health      # Quick health check (exit code)
uv run rd service start       # Start timer
uv run rd service stop        # Stop timer
uv run rd service restart     # Restart timer
uv run rd service logs        # Stream logs (interactive)
uv run rd service recent-logs # View recent logs (for scripts/agents)
uv run rd service install     # Install systemd files
uv run rd service uninstall   # Remove systemd files
```

### Configuration
```bash
uv run rd config show           # Show all config
uv run rd config set-key xai    # Set xAI API key
uv run rd config set-key gmail  # Set Gmail password
uv run rd config add-subreddit  # Add subreddit interactively
uv run rd config edit           # Open config in $EDITOR
```

### Rules
```bash
uv run rd rules show <sub>    # Show rules for subreddit
uv run rd rules set <sub>     # Set rules (reads stdin)
```

### Database
```bash
uv run rd db stats        # Show statistics
uv run rd db clear-seen   # Clear seen posts (reprocess all)
```

### Deployment
```bash
uv run rd deploy current      # Show current commit
uv run rd deploy history      # Show recent commits
uv run rd deploy test-run     # Test code works (dry run, no email)
uv run rd deploy test-run --send-email  # Test with real email
uv run rd deploy rollback X   # Rollback to commit X
```

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Timer/Cron  │────▶│ RSS Fetcher │────▶│ Grok Filter │
│ (30 min)    │     │ (per sub)   │     │ (approve?)  │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                          approved posts       │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Gmail SMTP  │◀────│ Grok HTML   │◀────│  SQLite DB  │
│ (send)      │     │ (style it)  │     │ (store)     │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Flow:**
1. Timer triggers every 30 minutes
2. Fetch new posts from each subreddit's RSS feed
3. For each unseen post, ask Grok: "Should this be in the digest?"
4. Store approved posts in SQLite with Grok's reason
5. If any new approved posts, ask Grok to generate styled HTML
6. Send email via Gmail SMTP
7. Mark posts as emailed

---

## Common Scenarios

### "I want to add a new feature"

1. Identify which file to modify (see File Reference above)
2. Make the change
3. Test: `uv run rd deploy test-run`
4. Commit: `git add -A && git commit -m "Add feature X"`
5. Restart: `uv run rd service restart`
6. Verify: `uv run rd service health`

### "I want to change how emails look"

Edit `src/reddit_digest/html_generator.py` - modify the prompt to Grok that describes how to style the email.

### "I want to change filtering behavior"

- For rule changes: Edit `config.yaml`
- For logic changes: Edit `src/reddit_digest/filter.py`

### "The service keeps failing"

```bash
# Get the error
uv run rd service recent-logs -n 100

# Common issues:
# - API key expired → uv run rd config set-key xai
# - Gmail password changed → uv run rd config set-key gmail
# - Rate limited → wait and retry
# - Code bug → fix and redeploy
```

### "I want to test without sending real emails"

Edit `emailer.py` temporarily to print HTML instead of sending, or comment out the `send_email()` call in `main.py`.

### "I need to run this on a different schedule"

Edit `systemd/reddit-digest.timer`, change `OnUnitActiveSec=30min` to your desired interval, then:

```bash
uv run rd service install   # Reinstall with new timer
uv run rd service restart
```
