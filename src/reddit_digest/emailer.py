"""Gmail SMTP email sender."""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


def send_email(
    html_content: str,
    plain_content: str,
    recipient: str | None = None,
    sender: str | None = None,
) -> None:
    """
    Send an HTML email via Gmail SMTP.

    Args:
        html_content: The HTML body of the email
        plain_content: Plain text fallback
        recipient: Override recipient email (defaults to config)
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
    if not sender or not recipient:
        from .config import load_config
        config = load_config()
        email_config = config.get("email", {})
        sender = sender or email_config.get("sender")
        recipient = recipient or email_config.get("recipient")

    if not sender or not recipient:
        raise ValueError("Email sender and recipient must be configured")

    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Reddit Digest - {datetime.now().strftime('%b %d, %I:%M %p')}"
    msg["From"] = sender
    msg["To"] = recipient

    # Attach both plain text and HTML versions
    part1 = MIMEText(plain_content, "plain")
    part2 = MIMEText(html_content, "html")
    msg.attach(part1)
    msg.attach(part2)

    # Send via SMTP
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())


def send_test_email(recipient: str | None = None) -> None:
    """Send a test email to verify configuration."""
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

    send_email(html, plain, recipient=recipient)
