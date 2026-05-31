import anthropic
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def load_scorer_prompt():
    """Load the scorer prompt from file."""
    with open ("prompts/scorer_prompt.txt","r") as f:
        return f.read()
    
def score_contract(red_flags):
    """Send red flags to claude and get overall risk score."""
    prompt = load_scorer_prompt()

    red_flags_text = json.dumps(red_flags, indent=2)

    response = client.messages.create(
        model = "claude-sonnet-4-5",
        max_tokens=500,
        messages=[
            {
                "role":"user",
                "content":f"{prompt}\n\nHere are the red flags found:\n\n{red_flags_text}"
            }
        ]
    )

    raw = response.content[0].text

    # Remove markdown code blocks if present
    raw = raw.replace("```json", "").replace("```", "").strip()

    result = json.loads(raw)
    return result
        