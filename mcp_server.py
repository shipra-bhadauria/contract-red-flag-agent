import os
import io
from dotenv import load_dotenv
import anthropic
from fastmcp import FastMCP

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

load_dotenv()

mcp = FastMCP("contract-red-flag-agent")

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_drive_service():
    """
    Returns authenticated Google Drive service object.
    First run : opens browser for google login - generates token.json.
    Subsequent runs: uses token.json directly.
    """

    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token_json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("drive", "v3" , credentials=creds)

@mcp.tool()
def fetch_from_drive(url: str) -> str:
    """
    Fetch a file from Google Drive using Drive API.
    Works with both public and private authorized files.
    Returns local temp file path.
    """
    import tempfile

    try:
        file_id = url.split("/d/")[1].split("/")[0]
    except IndexError:
        raise ValueError("Invalid Drive link - use: drive.google.com/file/d/FILE_ID/view")
    
    service = get_drive_service()
    file_metadata = service.files().get(
        fileId = file_id,
        fields = "name, mimeType"
    ).execute()

    mime_type = file_metadata.get("mimeType", "")
    suffix = ".txt" if "text" in mime_type else ".pdf"

    request = service.files().get_media(fileId = file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(buffer.getvalue())
    tmp.close()

    return tmp.name


if __name__ == "__main__":
    print("Starting Contract Red Flag MCP Server...")
    mcp.run()

