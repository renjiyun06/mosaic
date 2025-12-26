"""Email sending service"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ..config import settings
from ..logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """Email sending service (independent of event mesh)"""

    @staticmethod
    def send_verification_code(to_email: str, code: str) -> bool:
        """Send verification code email

        Args:
            to_email: Recipient email address
            code: Verification code

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Check SMTP configuration
            if not settings.smtp_user or not settings.smtp_password:
                logger.warning(
                    "SMTP configuration incomplete, skipping email send "
                    "(development mode)"
                )
                logger.info(f"Verification code: {code}")
                return True

            msg = MIMEMultipart()
            msg["From"] = (
                f"{settings.smtp_from_name} <{settings.smtp_from}>"
            )
            msg["To"] = to_email
            msg["Subject"] = "Mosaic - Email Verification Code"

            body = f"""
Hello,

Your verification code is: {code}

The code will expire in {settings.verification_code_expire_minutes} minutes.

If this was not you, please ignore this email.

---
Mosaic Team
            """.strip()

            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
            ) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info(f"Verification code email sent to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            # In development mode, print code even if email fails
            if settings.debug:
                logger.info(f"Verification code (dev mode): {code}")
                return True
            return False
