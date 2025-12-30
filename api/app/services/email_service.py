import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
import sentry_sdk

logger = logging.getLogger("uvicorn.error")

env = Environment(loader=FileSystemLoader("templates"))
verification_template = env.get_template("verification_email.html")


class EmailService:
    @staticmethod
    def send_verification_email(to_email: str, code: str):
        """
        Sends a verification email with the OTP code.
        """
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = os.getenv("SMTP_PORT")
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        smtp_auth_protocol = os.getenv("SMTP_AUTH_PROTOCOL", "TLS")
        smtp_from = os.getenv("SMTP_FROM_EMAIL")

        if not all([smtp_server, smtp_port, smtp_username, smtp_password]):
            logger.error(f"SMTP Config missing. Failed to send code {code} to {to_email}")
            return

        assert smtp_server is not None
        assert smtp_port is not None
        assert smtp_username is not None
        assert smtp_password is not None

        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg["Subject"] = "Verify your Meridian Account"

        html_content = verification_template.render(code=code)
        msg.attach(MIMEText(html_content, "html"))

        try:
            if smtp_auth_protocol.upper() == "SSL":
                with smtplib.SMTP_SSL(smtp_server, int(smtp_port)) as server:
                    server.login(smtp_username, smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
                    if smtp_auth_protocol.upper() == "STARTTLS":
                        server.starttls()
                    server.login(smtp_username, smtp_password)
                    server.send_message(msg)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to send email: {e}")
