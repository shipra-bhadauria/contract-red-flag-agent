import anthropic
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def load_questions_prompt():
    """Load the questions prompt from the file."""
    with open("prompts/questions_prompt.txt","r") as f:
        return f.read()
    
def generate_questions(red_flags):
    """Ask Claude to generate 3 smart questions based on red flags. """

    prompt = load_questions_prompt()
    red_flags_text = json.dumps(red_flags, indent=2)

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        messages=[
            {
                "role":"user",
                "content":f"{prompt}\n\nHere are the red flags:\n\n{red_flags_text}"
            }
        ]
    )

    raw = response.content[0].text

    # Remove markdown code blocks if present
    raw = raw.replace("```json", "").replace("```", "").strip()

    questions = json.loads(raw)
    return questions

        

    questions = json.loads(raw)
    return questions

def build_report(red_flags, score_result):
    """Combine everything into one clean report dictionary."""

    questions = generate_questions(red_flags)

    report = {
        "red_flags": red_flags,
        "risk_score": score_result["risk_score"],
        "verdict": score_result["verdict"],
        "summary": score_result["summary"],
        "questions": questions,
        "total_flags": len(red_flags),
        "high_flags": len([f for f in red_flags if f["severity"] == "high"]),
        "medium_flags": len([f for f in red_flags if f["severity"] == "medium"]),
        "low_flags" : len([f for f in red_flags if f["severity"] =="low"])

    }

    return report