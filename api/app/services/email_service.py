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
                <head>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                            line-height: 1.6;
                            color: #333;
                            max-width: 600px;
                            margin: 0 auto;
                            padding: 20px;
                        }}
                        .container {{
                            background-color: #f8f9fa;
                            border-radius: 8px;
                            padding: 30px;
                            text-align: center;
                        }}
                        .header {{
                            color: #1a1a1a;
                            margin-bottom: 20px;
                        }}
                        .code-box {{
                            background-color: #fff;
                            border: 2px solid #eb5e28;
                            border-radius: 6px;
                            padding: 20px;
                            margin: 25px 0;
                        }}
                        .code {{
                            color: #eb5e28;
                            font-size: 32px;
                            font-weight: bold;
                            letter-spacing: 8px;
                            margin: 0;
                        }}
                        .footer {{
                            color: #666;
                            font-size: 14px;
                            margin-top: 20px;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2 class="header">Welcome to Meridian!</h2>
                        <p>Thank you for signing up. Please use the verification code below to complete your registration:</p>
                        <div class="code-box">
                            <p class="code">{code}</p>
                        </div>
                        <p><strong>This code will expire in 15 minutes.</strong></p>
                        <div class="footer">
                            <p>If you didn't request this code, please ignore this email.</p>
                        </div>
                    </div>
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

        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to send email: {e}")
