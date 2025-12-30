import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import sentry_sdk

logger = logging.getLogger("uvicorn.error")


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
            logger.warning("SMTP configuration missing. Skipping email send (Log code: %s)", code)
            return

        assert smtp_server is not None
        assert smtp_port is not None
        assert smtp_username is not None
        assert smtp_password is not None

        try:
            msg = MIMEMultipart()
            msg["From"] = smtp_from
            msg["To"] = to_email
            msg["Subject"] = "Verify your Meridian Account"

            body = f"""
            <html>
                <body>
                    <h2>Welcome to Meridian!</h2>
                    <p>Please use the following code to verify your email address:</p>
                    <h1 style="color: #eb5e28; letter-spacing: 5px;">{code}</h1>
                    <p>This code will expire in 15 minutes.</p>
                </body>
            </html>
            """
            msg.attach(MIMEText(body, "html"))

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

            logger.info(f"Verification email sent to {to_email}")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to send email: {e}")
