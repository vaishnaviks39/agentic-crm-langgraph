import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def get_gmail_service():
    """Authenticate and return Gmail service."""
    creds = None

    # token.json stores credentials after first login
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # if no valid credentials login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # save credentials for next run
        with open("token.json", "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

@tool
def send_email(to: str, subject: str, body: str) -> dict:
    """Send a real email via Gmail to the given address."""
    try:
        service = get_gmail_service()

        # build email
        msg = MIMEMultipart()
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # encode and send
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw}
        ).execute()

        print(f"Email sent to {to} — Message ID: {result.get('id')}")
        return {"status": "sent", "message_id": result.get("id"), "to": to}

    except Exception as e:
        print(f"Email failed: {str(e)}")
        return {"status": "error", "error": str(e)}

'''
# test block
if __name__ == "__main__":
    result = send_email.invoke({
        "to": "test.email@gmail.com",
        "subject": "CRM Autopilot Tool Test",
        "body": "Testing send_email tool directly from gmail_tools.py"
    })
    print(result)
'''