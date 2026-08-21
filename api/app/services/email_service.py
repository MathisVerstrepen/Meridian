import asyncio
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import aiosmtplib
import boto3
import sentry_sdk
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("uvicorn.error")

env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parents[1] / "templates"))
verification_template = env.get_template("verification_email.html")


class EmailService:
    @staticmethod
    async def send_verification_email(to_email: str, code: str) -> None:
        """Send a verification email through the configured provider."""
        provider = os.getenv("EMAIL_PROVIDER", "smtp").strip().lower()
        subject = "Verify your Meridian Account"
        html_content = verification_template.render(code=code)

        if provider == "smtp":
            await EmailService._send_smtp(to_email, subject, html_content)
        elif provider == "ses":
            await EmailService._send_ses(to_email, subject, html_content)
        else:
            logger.error("Email provider configuration is invalid; message was not sent")

    @staticmethod
    async def _send_smtp(to_email: str, subject: str, html_content: str) -> None:
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = os.getenv("SMTP_PORT")
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        smtp_auth_protocol = os.getenv("SMTP_AUTH_PROTOCOL", "TLS")
        smtp_from = os.getenv("SMTP_FROM_EMAIL")

        if not all([smtp_server, smtp_port, smtp_username, smtp_password]):
            logger.error("SMTP configuration is incomplete; message was not sent")
            return

        assert smtp_server is not None
        assert smtp_port is not None
        assert smtp_username is not None
        assert smtp_password is not None

        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html"))

        try:
            use_implicit_ssl = smtp_auth_protocol.upper() == "SSL"

            client = aiosmtplib.SMTP(
                hostname=smtp_server,
                port=int(smtp_port),
                use_tls=use_implicit_ssl,
            )

            async with client:
                if not use_implicit_ssl and smtp_auth_protocol.upper() == "STARTTLS":
                    await client.starttls()

                await client.login(smtp_username, smtp_password)
                await client.send_message(msg)

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("SMTP delivery failed; message was not sent")

    @staticmethod
    async def _send_ses(to_email: str, subject: str, html_content: str) -> None:
        region = os.getenv("SES_REGION")
        from_email = os.getenv("SES_FROM_EMAIL")

        if not region or not from_email:
            logger.error("SES configuration is incomplete; message was not sent")
            return

        try:
            await asyncio.to_thread(
                EmailService._send_ses_sync,
                region,
                from_email,
                to_email,
                subject,
                html_content,
                os.getenv("SES_CONFIGURATION_SET_NAME"),
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("SES delivery failed; message was not sent")

    @staticmethod
    def _send_ses_sync(
        region: str,
        from_email: str,
        to_email: str,
        subject: str,
        html_content: str,
        configuration_set_name: str | None,
    ) -> None:
        client = boto3.client("sesv2", region_name=region)
        request: dict[str, Any] = {
            "FromEmailAddress": from_email,
            "Destination": {"ToAddresses": [to_email]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Html": {"Data": html_content, "Charset": "UTF-8"}},
                }
            },
        }
        if configuration_set_name:
            request["ConfigurationSetName"] = configuration_set_name

        client.send_email(**request)
