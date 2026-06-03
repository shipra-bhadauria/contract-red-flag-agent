import fitz  # PyMuPDF
import os
import base64
import anthropic
from dotenv import load_dotenv

load_dotenv()

def read_pdf(file_path):
    """Extract text from a PDF file."""
    text = ""
    doc = fitz.open(file_path)
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()

def read_txt(file_path):
    """Extract text from a .txt file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def read_image(file_path):
    """Extract text from a contract image using Claude Vision."""
    with open(file_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    elif ext == ".png":
        media_type = "image/png"
    elif ext == ".webp":
        media_type = "image/webp"
    else:
        raise ValueError(f"Unsupported image type: {ext}")

    vision_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = vision_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type":       "base64",
                            "media_type": media_type,
                            "data":       image_data,
                        }
                    },
                    {
                        "type": "text",
                        "text": "This is a contract document. Please extract all the text from this image exactly as it appears. Return only the extracted text, nothing else."
                    }
                ]
            }
        ]
    )
    return response.content[0].text


def extract_contract_text(file_path: str) -> str:
    """Main function — detects file type and extracts text."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return read_pdf(file_path)
    elif ext == ".txt":
        return read_txt(file_path)
    elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return read_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")