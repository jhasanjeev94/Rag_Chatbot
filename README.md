# Mutual Fund FAQ Assistant

A facts-only FAQ chatbot for HDFC Mutual Fund schemes, powered by a RAG (Retrieval-Augmented Generation) pipeline.

> ⚠️ **Disclaimer:** Facts-only. No investment advice.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GROQ_API_KEY
```

## Run

```bash
streamlit run app.py
```
