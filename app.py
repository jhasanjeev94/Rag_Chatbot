"""
Phase 6: Streamlit Chat UI
"""
import streamlit as st
import os

# Setup page config FIRST before any other st commands
st.set_page_config(
    page_title="Mutual Fund FAQ Assistant",
    page_icon="🏦",
    layout="centered"
)

# Set python path to allow imports since streamlit runs from its own context
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Safely import backend modules
from src.guardrails import screen_query
from src.retrieval.retriever import retrieve
from src.generation.generator import generate_answer
from src.guardrails.output_validator import validate_response

# --- UI Header ---
st.warning("⚠️ **Disclaimer**: Facts-only. No investment advice is provided.")

st.markdown("""
### Welcome! 👋
I am your factual assistant for **HDFC Mutual Fund** schemes. I can answer objective questions based strictly on the official scheme documents.
""")

# --- State Management ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "example_query" not in st.session_state:
    st.session_state.example_query = None

# --- Example Questions ---
st.markdown("**Try asking:**")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("💡 Expense ratio of Large Cap?"):
        st.session_state.example_query = "What is the expense ratio of HDFC Large Cap Fund?"
with col2:
    if st.button("💡 Exit load for Mid Cap?"):
        st.session_state.example_query = "What is the exit load for HDFC Mid Cap Fund?"
with col3:
    if st.button("💡 Min SIP for Small Cap?"):
        st.session_state.example_query = "What is the minimum SIP amount for HDFC Small Cap Fund?"

# --- Chat History ---
st.markdown("---")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat Input ---
user_input = st.chat_input("Type your question here...")

# Handle input from either text box or example buttons
query = user_input or st.session_state.example_query

if query:
    # Clear the example query state so it doesn't loop
    st.session_state.example_query = None
    
    # 1. Display user query
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
        
    # 2. Process Assistant Response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing query..."):
            # Pre-screen with guardrails
            screening = screen_query(query)
            
        if not screening['allowed']:
            response_text = screening['refusal_response']
            st.error("Blocked by safety guardrails")
            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})
        else:
            with st.spinner("Retrieving relevant facts..."):
                chunks = retrieve(query)
                
            if not chunks:
                response_text = "I don't have this information in my current sources."
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            else:
                with st.spinner("Generating answer..."):
                    raw_response = generate_answer(query, chunks)
                    validated = validate_response(raw_response)
                    
                    final_answer = validated['corrected_response']['answer']
                    
                    st.markdown(final_answer)
                    st.session_state.messages.append({"role": "assistant", "content": final_answer})
