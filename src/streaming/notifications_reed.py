"""Send notification emails with the Gmail API."""

from base64 import urlsafe_b64encode
from email.message import EmailMessage
import json
from pathlib import Path
from typing import Any, Final

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES: Final[list[str]] = ["https://www.googleapis.com/auth/gmail.send"]
CREDENTIALS_PATH: Final[Path] = Path("credentials.json")
TOKEN_PATH: Final[Path] = Path("token.json")


def token_has_required_scopes() -> bool:
    """Return whether the local token file includes the Gmail send scope.

    Returns:
        True when token.json contains all required scopes.
    """
    if not TOKEN_PATH.exists():
        return False

    try:
        token_data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except OSError:
        return False
    except json.JSONDecodeError:
        return False
    token_scopes = token_data.get("scopes", [])
    if isinstance(token_scopes, str):
        token_scopes = token_scopes.split()

    return set(SCOPES).issubset(set(token_scopes))


def get_gmail_credentials() -> Any:
    """Return valid Gmail API credentials.

    Returns:
        Valid Gmail API credentials with permission to send mail.

    Raises:
        FileNotFoundError: If credentials.json is not available.
    """
    creds: Any | None = None

    if token_has_required_scopes():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                msg = f"Missing Gmail OAuth client file: {CREDENTIALS_PATH}"
                raise FileNotFoundError(msg)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds


def send_sales_threshold_email(
    *,
    recipient_email: str,
    threshold: float,
    total_sales: float,
) -> dict[str, str]:
    """Send an email when total sales exceed the configured threshold.

    Args:
        recipient_email: Email address that should receive the notification.
        threshold: Configured sales alert threshold.
        total_sales: Current running total sales.

    Returns:
        Gmail API response metadata for the sent message.
    """
    message = EmailMessage()
    message["To"] = recipient_email
    message["From"] = "me"
    message["Subject"] = f"Sales threshold exceeded: ${total_sales:,.2f}"
    message.set_content(
        "The Kafka sales stream has exceeded the configured threshold.\n\n"
        f"Threshold: ${threshold:,.2f}\n"
        f"Total sales: ${total_sales:,.2f}\n"
    )

    encoded_message = urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    body = {"raw": encoded_message}

    service = build("gmail", "v1", credentials=get_gmail_credentials())
    result = service.users().messages().send(userId="me", body=body).execute()
    return {"id": result.get("id", ""), "threadId": result.get("threadId", "")}


if __name__ == "__main__":
    print("Import send_sales_threshold_email() from kafka_consumer_reed.py.")
