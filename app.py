import streamlit as st
import tempfile
import os
import datetime

from agent import run_agent, chat_with_agent, run_comparison
from mcp_server import fetch_from_drive

st.set_page_config(page_title="ContractLens", page_icon="⚖", layout="wide")

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
.masthead { display:flex; justify-content:space-between; align-items:center; padding-bottom:1rem; border-bottom:0.5px solid #E0DDD6; margin-bottom:1.5rem; }
.logo { font-size:20px; font-weight:600; }
.logo span { color:#8B6914; }
.badge { font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:#A0998C; border:0.5px solid #E0DDD6; padding:4px 10px; border-radius:20px; }
.slabel { font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:#A0998C; font-weight:500; margin-bottom:6px; }
.verdict { border-radius:8px; padding:14px; border-left:3px solid; margin:6px 0; }
.v-d { background:#FEF2F2; border-color:#B83232; color:#B83232; }
.v-w { background:#FFFBEB; border-color:#8B6914; color:#8B6914; }
.v-s { background:#F0FBF4; border-color:#2E7D4F; color:#2E7D4F; }
.v-title { font-size:16px; font-weight:600; margin-bottom:4px; }
.v-body { font-size:14px; color:#6A6460; line-height:1.65; }
.banner { border-radius:8px; padding:10px 14px; font-size:12px; line-height:1.6; margin:4px 0; }
.b-y { background:#FFFBEB; border:0.5px solid #D4A820; color:#8B6914; }
.b-g { background:#F0FBF4; border:0.5px solid #A8D8B8; color:#2E7D4F; }
.suggest { background:#F0FBF4; border:0.5px solid #A8D8B8; border-radius:6px; padding:10px; margin-top:8px; font-size:12px; color:#2E6040; }
.s-title { font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:#2E7D4F; font-weight:500; margin-bottom:4px; }
.q-item { display:flex; gap:10px; padding:8px 0; border-bottom:0.5px solid #EEEAE4; font-size:12px; color:#6A6460; line-height:1.6; }
.q-item:last-child { border-bottom:none; }
.q-num { font-size:16px; color:#D8D4CC; width:18px; flex-shrink:0; }
.pipe-row { display:flex; align-items:center; gap:8px; padding:5px 0; border-bottom:0.5px solid #EEEAE4; font-size:11px; }
.pipe-row:last-child { border-bottom:none; }
.dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
.dot-d { background:#2E7D4F; } .dot-i { background:#D8D4CC; }
.name-d { color:#2E7D4F; } .name-i { color:#C0BCB4; }
.risk-badge { font-size:11px; padding:3px 10px; border-radius:20px; font-weight:500; }
.rh { background:#FEF2F2; color:#B83232; }
.rm { background:#FFFBEB; color:#8B6914; }
.rl { background:#F0FBF4; color:#2E7D4F; }
</style>
""", unsafe_allow_html=True)

for k, v in {"messages": [], "report": None, "contract_text": "", "pipeline_steps": []}.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown('<div class="masthead"><div class="logo">Contract<span>Lens</span></div><div class="badge">LangGraph · Claude Vision · MCP</div></div>', unsafe_allow_html=True)

def make_report(r):
    lines = [
        "CONTRACTLENS REPORT",
        f"Date: {datetime.datetime.now().strftime('%d %b %Y')}",
        f"Verdict: {r.get('verdict','')}  |  Score: {r.get('risk_score','')}/100",
        f"Summary: {r.get('summary','')}", "", "RED FLAGS",
    ]
    for i, f in enumerate(r.get("red_flags", []), 1):
        lines += [
            f"{i}. {f.get('title','')} [{f.get('severity','').upper()}]",
            f"   {f.get('explanation','')}",
            f"   Suggested: {f.get('suggested_clause','')}", "",
        ]
    lines.append("QUESTIONS")
    for i, q in enumerate(r.get("questions", []), 1):
        lines.append(f"{i}. {q}")
    return "\n".join(lines)

tab1, tab2 = st.tabs(["Analyse", "Compare"])

# ═══════════════════════════════════════
# TAB 1 — ANALYSE
# ═══════════════════════════════════════

with tab1:
    L, _, R = st.columns([1, 0.05, 1.6])

    with L:
        st.markdown('<div class="slabel">Upload Contract</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader("f", type=["pdf","txt","jpg","jpeg","png","webp"], label_visibility="collapsed")

        st.markdown('<div class="slabel">Or Google Drive Link</div>', unsafe_allow_html=True)
        drive = st.text_input("d", placeholder="https://drive.google.com/file/d/...", label_visibility="collapsed")

        st.markdown('<div class="slabel">Or Paste Text</div>', unsafe_allow_html=True)
        pasted = st.text_area("t", height=90, placeholder="Paste contract here...", label_visibility="collapsed")

        st.markdown('<div class="slabel">Contract Type</div>', unsafe_allow_html=True)
        ctype = st.radio("ct", ["Employment","Freelance","NDA","Vendor","Lease","General"], horizontal=True, label_visibility="collapsed")

        analyse_btn = st.button("Analyse Contract →")

        if st.session_state.pipeline_steps:
            st.markdown('<div class="slabel" style="margin-top:14px;">Agent Pipeline</div>', unsafe_allow_html=True)
            steps = [
                ("extract_text","Text extraction"), ("analyze_clauses","Clause analysis"),
                ("score_risk","Risk scoring"), ("confidence_gate","Confidence gate"),
                ("reflection_check","Reflection check"), ("generate_report","Report generation"),
            ]
            done = set(st.session_state.pipeline_steps)
            st.markdown("".join(
                f'<div class="pipe-row"><div class="dot {"dot-d" if k in done else "dot-i"}"></div>'
                f'<span class="{"name-d" if k in done else "name-i"}">{l}</span></div>'
                for k, l in steps
            ), unsafe_allow_html=True)

    with R:
        if analyse_btn:
            if not uploaded and not drive.strip() and not pasted.strip():
                st.error("Please provide a contract.")
                st.stop()

            st.session_state.messages = []

            with st.spinner("Analysing..."):
                try:
                    tmp = None
                    if drive.strip():
                        tmp = fetch_from_drive(drive.strip())
                        st.session_state.contract_text = drive.strip()
                        report = run_agent(file_path=tmp, contract_type=ctype)
                    elif uploaded:
                        ext = os.path.splitext(uploaded.name)[1].lower()
                        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
                            f.write(uploaded.read())
                            tmp = f.name
                        st.session_state.contract_text = uploaded.name
                        report = run_agent(file_path=tmp, contract_type=ctype)
                    else:
                        st.session_state.contract_text = pasted
                        report = run_agent(raw_text=pasted, contract_type=ctype)

                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)

                    st.session_state.pipeline_steps = ["extract_text","analyze_clauses","score_risk","confidence_gate","reflection_check","generate_report"]
                    st.session_state.report = report

                except Exception as e:
                    st.error(f"Failed: {e}")
                    st.stop()

        if st.session_state.report:
            r = st.session_state.report

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Risk Score", f"{r.get('risk_score',0)}/100")
            m2.metric("Red Flags",  r.get("total_flags", 0))
            m3.metric("High",       r.get("high_flags", 0))
            m4.metric("Medium",     r.get("medium_flags", 0))

            score = r.get("risk_score", 0)
            css, icon = ("v-d","✕") if score > 75 else ("v-w","⚠") if score > 25 else ("v-s","✓")
            st.markdown(f'<div class="verdict {css}"><div class="v-title">{icon} {r.get("verdict","")}</div><div class="v-body">{r.get("summary","")}</div></div>', unsafe_allow_html=True)

            if r.get("human_review_required"):
                st.markdown(f'<div class="banner b-y">⚠ <strong>Human review recommended</strong> — {r.get("review_reason","")}</div>', unsafe_allow_html=True)
            if r.get("reflection_note"):
                icon_r = "✓" if r.get("reflection_passed") else "◎"
                st.markdown(f'<div class="banner b-g">{icon_r} <strong>Reflection</strong> — {r.get("reflection_note","")}</div>', unsafe_allow_html=True)

            st.markdown(f'<div class="slabel" style="margin-top:12px;">Red Flags — {len(r.get("red_flags",[]))} issues</div>', unsafe_allow_html=True)

            clr = {"high":"#B83232","medium":"#8B6914","low":"#2E7D4F"}
            lbl = {"high":"● High","medium":"◉ Medium","low":"○ Low"}

            for i, flag in enumerate(r.get("red_flags", [])):
                sev = flag.get("severity","low")
                with st.expander(flag.get("title",""), expanded=(i==0 and sev=="high")):
                    st.markdown(f'<span style="font-size:10px;font-weight:600;text-transform:uppercase;color:{clr.get(sev)}">{lbl.get(sev)}</span>', unsafe_allow_html=True)
                    st.markdown('<div style="font-size:10px;color:#A0998C;margin:8px 0 4px;">Problematic Clause</div>', unsafe_allow_html=True)
                    st.code(flag.get("clause",""), language=None)
                    st.markdown('<div style="font-size:10px;color:#A0998C;margin:8px 0 4px;">Why It\'s Risky</div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="font-size:12px;color:#6A6460;line-height:1.65;">{flag.get("explanation","")}</div>', unsafe_allow_html=True)
                    if flag.get("suggested_clause"):
                        st.markdown(f'<div class="suggest"><div class="s-title">Suggested Clause</div>{flag["suggested_clause"]}</div>', unsafe_allow_html=True)

            if r.get("questions"):
                st.markdown('<div class="slabel" style="margin-top:12px;">Questions to Ask Before Signing</div>', unsafe_allow_html=True)
                st.markdown("".join(
                    f'<div class="q-item"><div class="q-num">{i}</div><div>{q}</div></div>'
                    for i, q in enumerate(r.get("questions",[]), 1)
                ), unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.download_button("⬇ Download Report", data=make_report(r),
                    file_name=f"contractlens_{datetime.datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain")
            with c2:
                if st.button("↺ New Analysis"):
                    st.session_state.update({"report":None,"messages":[],"contract_text":"","pipeline_steps":[]})
                    st.rerun()

            st.markdown('<div class="slabel" style="margin-top:12px;">Ask About This Contract</div>', unsafe_allow_html=True)
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

            if ui := st.chat_input("Ask anything..."):
                st.session_state.messages.append({"role":"user","content":ui})
                with st.chat_message("user"): st.write(ui)
                with st.chat_message("assistant"):
                    with st.spinner(""):
                        reply = chat_with_agent(ui, r, st.session_state.contract_text)
                    st.write(reply)
                st.session_state.messages.append({"role":"assistant","content":reply})

        else:
            st.markdown("""
            <div style="height:360px;display:flex;flex-direction:column;align-items:center;
                justify-content:center;border:0.5px dashed #E0DDD6;border-radius:12px;gap:12px;">
                <div style="font-size:30px;opacity:0.2;">⚖</div>
                <div style="font-size:15px;font-weight:500;color:#C0BCB4;">No contract analysed yet</div>
                <div style="font-size:12px;color:#C8C4BC;text-align:center;max-width:200px;line-height:1.6;">
                    Upload a file, Drive link, or paste text on the left.
                </div>
            </div>
            """, unsafe_allow_html=True)

# ═══════════════════════════════════════
# TAB 2 — COMPARE
# ═══════════════════════════════════════

# ═══════════════════════════════════════
# TAB 2 — COMPARE
# ═══════════════════════════════════════

with tab2:
    st.markdown('<div style="font-size:17px;font-weight:600;margin-bottom:6px;">Compare Two Contracts</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:12px;color:#A0998C;margin-bottom:16px;">Upload or paste two contracts — agent compares risk and highlights key differences.</div>', unsafe_allow_html=True)

    ca_col, cb_col = st.columns(2)

    with ca_col:
        st.markdown('<div class="slabel">Contract A</div>', unsafe_allow_html=True)
        ca_file   = st.file_uploader("ca_file", type=["pdf","txt","jpg","jpeg","png","webp"], label_visibility="collapsed", key="ca_file")
        ca_drive  = st.text_input("ca_drive", placeholder="Or Drive link...", label_visibility="collapsed", key="ca_drive")
        ca_text   = st.text_area("ca_text", height=120, placeholder="Or paste contract A...", label_visibility="collapsed", key="ca_text")

    with cb_col:
        st.markdown('<div class="slabel">Contract B</div>', unsafe_allow_html=True)
        cb_file   = st.file_uploader("cb_file", type=["pdf","txt","jpg","jpeg","png","webp"], label_visibility="collapsed", key="cb_file")
        cb_drive  = st.text_input("cb_drive", placeholder="Or Drive link...", label_visibility="collapsed", key="cb_drive")
        cb_text   = st.text_area("cb_text", height=120, placeholder="Or paste contract B...", label_visibility="collapsed", key="cb_text")

    if st.button("Compare Contracts →", key="cmp"):
        # Input resolve karo — file > drive > text priority
        def resolve_input(file, drive, text):
            if file:
                ext = os.path.splitext(file.name)[1].lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
                    f.write(file.read())
                    tmp = f.name
                from tools.pdf_reader import extract_contract_text
                content = extract_contract_text(tmp)
                os.unlink(tmp)
                return content
            elif drive.strip():
                tmp = fetch_from_drive(drive.strip())
                from tools.pdf_reader import extract_contract_text
                content = extract_contract_text(tmp)
                os.unlink(tmp)
                return content
            elif text.strip():
                return text.strip()
            return None

        if not (ca_file or ca_drive.strip() or ca_text.strip()) or \
           not (cb_file or cb_drive.strip() or cb_text.strip()):
            st.error("Please provide both contracts.")
        else:
            with st.spinner("Comparing..."):
                try:
                    text_a = resolve_input(ca_file, ca_drive, ca_text)
                    text_b = resolve_input(cb_file, cb_drive, cb_text)

                    res = run_comparison(text_a, text_b)
                    rc  = {"low":"rl","medium":"rm","high":"rh"}

                    r1, r2 = st.columns(2)
                    with r1:
                        st.markdown(f"""
                        <div style="background:#FDFCFA;border:0.5px solid #E0DDD6;border-radius:8px;padding:14px;">
                            <div class="slabel">Contract A</div>
                            <div style="font-size:15px;font-weight:600;margin-bottom:6px;">{res.get('contract_a_verdict','')}</div>
                            <span class="risk-badge {rc.get(res.get('contract_a_risk',''),'rm')}">{res.get('contract_a_risk','').title()} Risk</span>
                        </div>
                        """, unsafe_allow_html=True)
                    with r2:
                        st.markdown(f"""
                        <div style="background:#FDFCFA;border:0.5px solid #E0DDD6;border-radius:8px;padding:14px;">
                            <div class="slabel">Contract B</div>
                            <div style="font-size:15px;font-weight:600;margin-bottom:6px;">{res.get('contract_b_verdict','')}</div>
                            <span class="risk-badge {rc.get(res.get('contract_b_risk',''),'rm')}">{res.get('contract_b_risk','').title()} Risk</span>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown('<div class="slabel" style="margin-top:14px;">Key Differences</div>', unsafe_allow_html=True)
                    st.markdown("".join(
                        f'<div class="q-item"><div class="q-num">—</div><div>{d}</div></div>'
                        for d in res.get("key_differences",[])
                    ), unsafe_allow_html=True)

                    if res.get("safer_contract"):
                        st.markdown(f'<div style="display:inline-block;font-size:12px;padding:5px 14px;border-radius:20px;background:#F0FBF4;color:#2E7D4F;border:0.5px solid #A8D8B8;font-weight:500;margin-top:10px;">✓ Contract {res["safer_contract"]} is safer</div>', unsafe_allow_html=True)

                    st.markdown(f"""
                    <div style="background:#FDF6E8;border:0.5px solid #E8D8A8;border-radius:8px;padding:14px;margin-top:10px;">
                        <div class="slabel" style="color:#8B6914;">Recommendation</div>
                        <div style="font-size:12px;color:#6A4A0A;line-height:1.65;margin-top:4px;">{res.get('recommendation','')}</div>
                    </div>
                    """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Failed: {e}")