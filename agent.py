import anthropic
import os 
import json 

from tools.pdf_reader import extract_contract_text
from tools.analyzer import analyze_contract
from tools.scorer import score_contract
from tools.reporter import build_report

from dotenv import load_dotenv

load_dotenv()

def run_agent(file_path=None, raw_text=None):
    """Main agent function - orchestrates all tools."""

    #step 1 - get contract text
    if file_path:
        print("Reading contract from file...")
        contract_text = extract_contract_text(file_path)
    elif raw_text:
        print("Reading contract from text...")
        contract_text = raw_text
    else:
        raise ValueError("Provide either file_path or raw_text")


    #step 2 - Analyze contract
    print("Analyzing contract for red flags...")
    red_flags = analyze_contract(contract_text)

    #step 3 - Score contract
    print("Scoring overall risk...")
    score_result = score_contract(red_flags)

    #step 4 - Build report
    print("Building final report")
    report = build_report(red_flags, score_result)

    print("Done!")
    return report

def chat_with_agent(user_message, report, contract_text):
    """Allow user to ask follow-up questions about the contract."""

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    #Build context from report
    context = f"""
You are a contract law expert. You have already analyzed the contract and found the following:

VERDICT : {report['verdict']}
RISK SCORE : {report['risk_score']}/100
SUMMARY: {report['summary']}

RED FLAGS FOUND:
{json.dumps(report['red_flags'], indent=2)}

QUESTIONS SUGGESTED:
{json.dumps(report['questions'], indent=2)}

ORIGINAL CONTRACT TEXT:
{contract_text}

Now answer the user's follow-up questions about this contract.
Be specific, helpful, and reference actual clauses when relevant.
Keep your answer concise — maximum 250 words.
"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[
            {
                "role":"user",
                "content": f"{context}\n\n User question: {user_message}"
            }
        ]
    )

    return response.content[0].text

