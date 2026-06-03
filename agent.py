import anthropic
import os 
import json 
from typing import TypedDict
from dotenv import load_dotenv

from langgraph.graph import StateGraph , START, END

from tools.pdf_reader import extract_contract_text
from tools.analyzer import analyze_contract
from tools.scorer import score_contract
from tools.reporter import build_report

from dotenv import load_dotenv

load_dotenv()

class ContractState(TypedDict):
    file_path : str | None
    raw_text : str | None
    contract_type : str
    contract_text : str
    red_flags : list
    score_result : dict
    low_confidence : bool
    confidence_ok : bool
    needs_human_review : bool
    review_reason : str
    reflection_passed : bool
    reflection_note : str
    report : dict
    error : str | None





def node_extract_text(state : ContractState) -> ContractState:
    try:
        if state.get("file_path"):
            text = extract_contract_text(state["file_path"])
        elif state.get("raw_text"):
            text = state["raw_text"]
        else:
            return {**state, "error": "No input provided - supply file_path or raw_text."}
        return {**state, "contract_text": text, "error": None}
    except Exception as e:
        return {**state, "error": f"Text extraction failed: {e}"}
    
# ── Node 2: analyze_clauses ────────────────────────────────────────────────
# Sends contract text to Claude and gets red flags back.

def node_analyze_clauses(state: ContractState) -> ContractState:
    if state.get("error"):
        return state
    try:
        result = analyze_contract(state["contract_text"])
        return {
            **state,
            "red_flags" : result.get("red_flags", []),
            "low_confidence" : result.get("low_confidence", False)
        }
    except Exception as e:
        return {**state, "error": f"Clause analysis failed: {e}"}
    
# ── Node 3: score_risk ─────────────────────────────────────────────────────
# Takes red flags and calculates overall risk score + confidence_level.
# Calls score_contract() which uses scorer_prompt.txt.

def node_score_risk(state: ContractState) -> ContractState:
    if state.get("error"):
        return state
    try:
        score_result = score_contract(state["red_flags"])
        return {**state, "score_result": score_result}
    except Exception as e:
        return {**state, "error": f"Risk scoring failed: {e}"}
    
# ── Node 4: confidence_gate ────

def node_confidence_gate(state: ContractState) -> ContractState:
    if state.get("error"):
        return state
    
    red_flags = state.get("red_flags", [])
    score_result = state.get("score_result", {})
    score = score_result.get("risk_score", 0)
    conf_level = score_result.get("confidence_level", "high")
    low_conf_flag = state.get("low_confidence", False)
    high_flags = [f for f in red_flags if f.get("severity") == "high"]

    ambiguous_score = 38 <= score <= 62 and len(high_flags) == 0
    scorer_uncertain = conf_level =="low"
    analyzer_unsure = low_conf_flag is True

    if ambiguous_score or scorer_uncertain or analyzer_unsure:
        if analyzer_unsure:
            reason = "Contract text was too short or garbled - extraction may not be reliable."
        elif ambiguous_score:
            reason = "Risk score is in an ambiguous range with no high severity flags -  a legal professional should verify."
        else:
            reason = "Scorer reported low confidence - human review recommended before acting on this verdict."

        return {
            **state,
            "confidence_ok": False,
            "needs_human_review": True,
            "review_reason" : reason,
        }
    
    return {
        **state,
        "confidence_ok": True,
        "needs_human_review": False,
        "review_reason": "",
    }

# ── Node 5: human_review_flag ───
# needs_human_review is already set in state by confidence_gate.

def node_human_review_flag(state: ContractState) -> ContractState:
    return state

# ── Node 6: reflection_check ───────────────────────────────────────────────
# New node — implements the reflection pattern.

def node_reflection_check(state: ContractState) -> ContractState:
    if state.get("error"):
        return state
    
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    red_flags_text = json.dumps(state.get("red_flags", []), indent=2)
    contract_expert = state.get("contract_text", "")[:3000]
    
    prompt = f"""You are a senior contract lawyer doing a quality check.
    A junior lawyer reviewd this contract and found these red flags:
    {red_flags_text}

    Here is the beginning of the contract:
    {contract_expert}

    Check if the review looks complete:
    -Are there obvious clause types not checked ? (termination, IP, payment, liability, non-compete)
    -Does the number of flags seem reasonable for this contract length?

    Return ONLY JSON:
    {{
    "reflection_passed" : true or false,
    "reflecttion_note" : "One sentence - either 'Review looks complete.' or describe what might be missing."
    
    }}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=200,
            messages=[
                {
                    "role":"user",
                    "content":prompt
                }
            ]
        )
        raw = response.content[0].text.replace("```json", "").replace("```","").strip()
        result = json.loads(raw)
        return {
            **state,
            "reflection_passed": result.get("reflection_passed", True),
            "reflection_note": result.get("reflection_note", "Review looks complete.")
        }
    
    except Exception:
        return {**state, "reflection_passed":True, "reflection_note":"Reflection check skipped."}
    
# ── Node 7: generate_report ──
# Calls reporter.py's build_report() which also generates questions.
def node_generate_report(state: ContractState) -> ContractState:
    if state.get("error"):
        return state
    try: 
        report = build_report(state["red_flags"], state["score_result"])

        report["human_review_required"] = state.get("needs_human_review", False)
        report["review_reason"] = state.get("review_reason", "")
        report["reflection_passed"] = state.get("reflection_passed", True)
        report["reflection_note"] = state.get("reflection_note","")

        return {**state, "report" : report}
    except Exception as e:
        return {**state, "error": f"Report generation failed: {e}"}
    
# ── Routing functions ────
# Used by conditional edges to determine the next node.
# Read state and return a string matching a node name.

def route_confidence(state : ContractState) -> str:
    if state.get("error"):
        return "reflection_check"
    if not state.get("confidence_ok"):
        return "human_review_flag"
    return "reflection_check"

def route_after_human_flag(state: ContractState) -> str:
    return "reflection_check"

# ── Graph assembly ─────────────────────────────────────────────────────────
# All nodes and edges connected here.
# compile() turns the graph into a runnable object.
 
def build_graph():
    g = StateGraph(ContractState)

    g.add_node("extract_text", node_extract_text)
    g.add_node("analyze_clauses", node_analyze_clauses)
    g.add_node("score_risk", node_score_risk)
    g.add_node("confidence_gate", node_confidence_gate)
    g.add_node("human_review_flag", node_human_review_flag)
    g.add_node("reflection_check", node_reflection_check)
    g.add_node("generate_report", node_generate_report)

    g.set_entry_point("extract_text")

    g.add_edge("extract_text", "analyze_clauses")
    g.add_edge("analyze_clauses", "score_risk")
    g.add_edge("score_risk", "confidence_gate")

    g.add_conditional_edges(
        "confidence_gate",
        route_confidence,
        {
            "human_review_flag": "human_review_flag",
            "reflection_check": "reflection_check",
        }
    )

    g.add_conditional_edges(
        "human_review_flag",
        route_after_human_flag,
        {"reflection_check": "reflection_check"} 
    )
    
    g.add_edge("reflection_check", "generate_report")
    g.add_edge("generate_report", END)

    return g.compile()

_graph = build_graph()

# ── Public API ─────────────────────────────────────────────────────────────
# These are the only two functions app.py calls.
# run_agent() invokes the full graph.
# chat_with_agent() handles follow-up questions — runs outside the graph.

def run_agent(file_path=None, raw_text= None, contract_type = "General") -> dict:
    initial_state: ContractState = {
        "file_path" : file_path,
        "raw_text" : raw_text,
        "contract_type" : contract_type,
        "contract_text" : "",
        "red_flags": [],
        "score_result":{},
        "low_confidence": False,
        "confidence_ok" : False,
        "needs_human_review":False,
        "review_reason": "",
        "reflection_passed" : True,
        "reflection_note" : "",
        "report" : {},
        "error" : None,
    }

    final_state = _graph.invoke(initial_state)

    if final_state.get("error"):
        raise RuntimeError(final_state["error"])
    return final_state["report"]

def chat_with_agent(user_message: str, report: dict, contract_text: str) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    context = f"""
        You are a contract law expert . You have already analyzed the contract.

        VERDICT : {report['verdict']}
        RISK SCORE : {report['risk_score']}/100
        SUMMARY : {report['summary']}

        RED FLAGS:
        {json.dumps(report['red_flags'], indent=2)}

        QUESTIONS SUGGESTED:
        {json.dumps(report.get('questions',[]), indent=2)}

        ORIGINAL CONTRACT TEXT:
        {contract_text}

        Answer the user's follow up question. Be specific, reference actual clauses.
        Maximum 250 words. Plain English.
""" 
        
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[{
            "role":"user",
            "content": f"{context}\n\n User question: {user_message}"
        }]
    )
    return response.content[0].text

def run_comparison(contract_a: str, contract_b: str) -> dict:
    """
    Compare two contracts and return a risk comparison report.
    Called directly by app.py — does not go through LangGraph graph.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""You are a contract lawyer comparing two contract drafts.

CONTRACT A:
{contract_a[:3000]}

CONTRACT B:
{contract_b[:3000]}

Return ONLY JSON:
{{
  "contract_a_risk": "low" or "medium" or "high",
  "contract_b_risk": "low" or "medium" or "high",
  "contract_a_verdict": "one word verdict",
  "contract_b_verdict": "one word verdict",
  "key_differences": [
    "difference 1",
    "difference 2",
    "difference 3"
  ],
  "safer_contract": "A" or "B",
  "recommendation": "Which is safer and why — 2 sentences max."
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )

    raw    = response.content[0].text.replace("```json", "").replace("```", "").strip()
    result = json.loads(raw)
    return result
    