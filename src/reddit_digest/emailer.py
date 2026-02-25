"""Gmail SMTP email sender."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)


def _get_recipients_from_config() -> list[str]:
    """Get recipient list from config, handling both old and new formats."""
    from .config import load_config
    config = load_config()
    email_config = config.get("email", {})

    # Support both 'recipients' (list) and 'recipient' (string) for backward compat
    recipients = email_config.get("recipients")
    if recipients:
        return recipients if isinstance(recipients, list) else [recipients]

    # Fall back to old 'recipient' field
    recipient = email_config.get("recipient")
    if recipient:
        return [recipient]

    return []


def send_email(
    html_content: str,
    plain_content: str,
    recipients: list[str] | str | None = None,
    sender: str | None = None,
) -> None:
    """
    Send an HTML email via Gmail SMTP to one or more recipients.

    Args:
        html_content: The HTML body of the email
        plain_content: Plain text fallback
        recipients: Override recipient email(s) (defaults to config)
                    Can be a list of emails or a single email string
        sender: Override sender email (defaults to config)

    Raises:
        ValueError: If required config is missing
        smtplib.SMTPException: If sending fails
    """
    # Get credentials from environment
    password = os.getenv("GMAIL_APP_PASSWORD")
    if not password:
        raise ValueError("GMAIL_APP_PASSWORD environment variable not set")

    # Load email config if not overridden
    if not sender:
        from .config import load_config
        config = load_config()
        email_config = config.get("email", {})
        sender = email_config.get("sender")

    # Normalize recipients to a list
    if recipients is None:
        recipients = _get_recipients_from_config()
    elif isinstance(recipients, str):
        recipients = [recipients]

    if not sender:
        raise ValueError("Email sender must be configured")
    if not recipients:
        raise ValueError("At least one email recipient must be configured")

    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    # Send to each recipient individually (more reliable than BCC)
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, password)

        for recipient in recipients:
            # Create message for each recipient
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Reddit Digest - {datetime.now().strftime('%b %d, %I:%M %p')}"
            msg["From"] = sender
            msg["To"] = recipient

            # Attach both plain text and HTML versions
            part1 = MIMEText(plain_content, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)

            server.sendmail(sender, recipient, msg.as_string())
            logger.info(f"Email sent to {recipient}")


def send_test_email(recipients: list[str] | str | None = None) -> None:
    """Send a test email to verify configuration.

    Args:
        recipients: Override recipient(s). If None, uses config.
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; }
            .content { padding: 20px; background: #f5f5f5; border-radius: 10px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Reddit Digest Test</h1>
            <p>Your configuration is working!</p>
        </div>
        <div class="content">
            <p>If you're seeing this email, your Reddit Digest is configured correctly.</p>
            <p>You'll start receiving curated posts from your configured subreddits.</p>
        </div>
    </body>
    </html>
    """

    plain = """
    Reddit Digest Test
    ==================

    Your configuration is working!

    If you're seeing this email, your Reddit Digest is configured correctly.
    You'll start receiving curated posts from your configured subreddits.
    """

    send_email(html, plain, recipients=recipients)
