import streamlit as st
import tempfile
import os
from agent import run_agent, chat_with_agent

st.set_page_config(
    page_title="Contract Red Flag Agent",
    page_icon="📄",
    layout="wide"
)

#Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "report" not in st.session_state:
    st.session_state.report = None

if "contract_text" not in st.session_state:
    st.session_state.contract_text = None

st.title("📄 Contract Red Flag Agent")
st.caption("Powered by Claude")

#Layout - 2 columns
left, right = st.columns([1, 1.4])

with left:
    st.subheader("Upload Contract")

    #File uploader
    uploaded_file = st.file_uploader(
        "Drag and drop or click the upload",
        type=["pdf","txt", "jpg", "jpeg", "png", "webp"],
        help= "PDF or .txt files supported"
    )

    st.divider()
    st.write("**Or paste contract text**")

    #Text area
    pasted_text = st.text_area(
        "Paste Contract here",
        height= 150,
        placeholder="Place your contract text here..."
    )

    #Contract type
    st.write("**Contract Type**")
    contract_type = st.radio(
        "Select type",
        ["Freelance", "Employment", "NDA", "Vendor", "Lease"],
        horizontal=True,
        label_visibility="collapsed"
    )

    #Analyze button
    analyze_button = st.button(
        "🔍 Analyze Contract",
        type="primary",
        use_container_width=True
    )

with right:
    if analyze_button:
        #Validate input
        if not uploaded_file and not pasted_text.strip():
            st.error("Please upload a file or paste contract text!")

        else:
            with st.spinner("Agent is analyzing your contract..."):

                #Get contract text
                if uploaded_file:
                    #Save uploaded file temporarily
                    ext = os.path.splitext(uploaded_file.name)[1].lower()
                    suffix = ext
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded_file.read())
                        tmp_path = tmp.name
                         
                    report = run_agent(file_path=tmp_path)
                    os.unlink(tmp_path)

                else:
                    report = run_agent(raw_text=pasted_text)


                #Save to session state
                st.session_state.report = report
                st.session_state.contract_text = pasted_text if pasted_text else uploaded_file.name
                st.session_state.messages = []

            #Metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Red Flags", report["total_flags"])
            col2.metric("High Severity", report["high_flags"])
            col3.metric("Risk score", f"{report['risk_score']}/100")

            st.divider() 

            #VERDICT
            verdict = report["verdict"]
            if "Not" in verdict or "Do" in verdict:
                st.error(f"🔴 {verdict}")
            elif "High" in verdict:
                st.warning(f"🟠 {verdict}")
            elif "Review" in verdict:
                st.warning(f"🟡 {verdict}")
            else:
                st.success(f"🟢 {verdict}")

            st.write(report["summary"])

            st.divider()

            #---Red Flags-----
            st.subheader("🚨 Red Flags Found")

            for flag in report["red_flags"]:
                severity = flag["severity"]

                if severity == "high":
                    color = "🔴"
                elif severity == "medium":
                    solor = "🟠"
                else:
                    color = "🟢"

                with st.expander(f"{color} [{severity.upper()}] {flag['title']}"):
                    st.code(flag["clause"], language=None)
                    st.write(flag["explanation"])

                    #Suggested clause
                    if "suggested_clause" in flag:
                        st.success(f"✅ **Suggested clause** {flag['suggested_clause']}")

            st.divider()

            #---QUESTIONS---
            st.subheader("❓ Questions to Ask Before Signing") 
            for i, q in enumerate(report["questions"], 1):
                st.write(f"**{i}.** {q}") 

    else:
        #Placeholder when no analysis yet
        st.info("👈 Upload a contract or paste text, then click Analuze!")   


    #CHAT SECTION
    if st.session_state.report is not None:
        st.divider()
        st.subheader("💬 Ask about this contract")

        #Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        #Chat input
        user_input = st.chat_input("Ask anything about contract.")

        if user_input:
            #Add user message to history
            st.session_state.messages.append({
                "role":"user",
                "content": user_input
            })

            #Show user message
            with st.chat_message("user"):
                st.write(user_input)

            #Get agent response
            with st.chat_message("assistant"):
                with st.spinner("Thinking.."):
                    response = chat_with_agent(
                        user_input,
                        st.session_state.report,
                        st.session_state.contract_text
                    )   
                st.write(response)

            #Add assistant response to history
            st.session_state.messages.append({
                "role":"assistant",
                "content": response
            })
