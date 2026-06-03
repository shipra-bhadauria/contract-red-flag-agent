import anthropic 
import json
import os
from dotenv import load_dotenv
import re

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def load_prompt():
    """ Load the red flag prompt from file."""
    with open("prompts/red_flag_prompt.txt","r") as f:
        return f.read()
    
def analyze_contract(contract_text):
    """Send contract to Claude and get red flags back. """

    prompt = load_prompt()

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        messages=[
            {
                "role":"user",
                "content": f"{prompt}\n\nHere is the contract to analyze:\n\n{contract_text}"
            }
        ]
    )

    raw = response.content[0].text
    raw = response.content[0].text
    
    raw = raw.replace("```json", "").replace("```","").strip()

    result = json.loads(raw)
    return result
    