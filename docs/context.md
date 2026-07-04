# Project Context — Mutual Fund FAQ Assistant

## 1. What We're Building

A **facts-only FAQ chatbot** for mutual fund schemes, using **Groww** as the reference product context. The system uses a **Retrieval-Augmented Generation (RAG)** pipeline to answer objective, verifiable questions by retrieving information exclusively from official public sources.

> **Core principle:** Accuracy over intelligence — every response must be factual, source-backed, and free of advisory bias.

---

## 2. Target Users

| Audience | Use-case |
|---|---|
| Retail investors | Comparing mutual fund schemes on factual parameters (expense ratio, exit load, SIP minimums, etc.) |
| Customer support / content teams | Handling repetitive mutual fund queries with consistent, citation-backed answers |

---

## 3. Corpus & Data Sources

### AMC Selection
- **AMC:** HDFC Mutual Fund (HDFC Asset Management Company)
- **Schemes (5):** Selected for category diversity across equity and commodity segments

| # | Scheme | Category | Groww URL |
|---|--------|----------|-----------|
| 1 | HDFC Large Cap Fund – Direct Plan Growth | Large Cap (Equity) | [Link](https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth) |
| 2 | HDFC Mid Cap Fund – Direct Plan Growth | Mid Cap (Equity) | [Link](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth) |
| 3 | HDFC Small Cap Fund – Direct Plan Growth | Small Cap (Equity) | [Link](https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth) |
| 4 | HDFC Gold ETF Fund of Fund – Direct Plan Growth | Gold ETF FoF (Commodity) | [Link](https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth) |
| 5 | HDFC Silver ETF FoF – Direct Plan Growth | Silver ETF FoF (Commodity) | [Link](https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth) |

### Document Sources (Primary Corpus URLs)

The following **5 Groww scheme pages** serve as the primary corpus for RAG ingestion. Each page aggregates key scheme data (NAV, expense ratio, exit load, holdings, risk, SIP details, etc.) from official sources:

| # | Scheme | Corpus URL |
|---|--------|------------|
| 1 | HDFC Large Cap Fund – Direct Plan Growth | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| 2 | HDFC Mid Cap Fund – Direct Plan Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| 3 | HDFC Small Cap Fund – Direct Plan Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| 4 | HDFC Gold ETF Fund of Fund – Direct Plan Growth | https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth |
| 5 | HDFC Silver ETF FoF – Direct Plan Growth | https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth |

#### Supplementary Sources (optional expansion)
Additional official URLs may be added later for deeper coverage:
- Scheme factsheets & KIM / SID documents (from HDFC MF)
- AMC FAQ / help pages
- AMFI / SEBI guidance pages
- Statement & tax document download guides

### Allowed Sources
- ✅ Official AMC websites
- ✅ AMFI (amfiindia.com)
- ✅ SEBI (sebi.gov.in)
- ❌ Third-party blogs, aggregator sites, or unofficial content

---

## 4. Functional Requirements

### 4.1 Answerable Query Types (Facts-Only)
The assistant answers **objective, verifiable** questions such as:
- Expense ratio of a scheme
- Exit load details
- Minimum SIP amount
- ELSS lock-in period
- Riskometer classification
- Benchmark index
- Process to download statements or capital gains reports

### 4.2 Response Format Rules
Every response **must**:
1. Be limited to a **maximum of 3 sentences**
2. Include **exactly one citation link** to the source
3. Include a footer: `"Last updated from sources: <date>"`

### 4.3 Refusal Handling
The assistant **must refuse** non-factual or advisory queries (e.g., *"Should I invest in this fund?"*, *"Which fund is better?"*).

Refusal responses must:
- Be polite and clearly worded
- Reinforce the facts-only limitation
- Provide a relevant educational link (e.g., AMFI or SEBI resource)

---

## 5. Hard Constraints

### Privacy & Security
The system must **never** collect, store, or process:
- PAN or Aadhaar numbers
- Account numbers
- OTPs
- Email addresses or phone numbers

### Content Restrictions
- No investment advice or recommendations
- No performance comparisons or return calculations
- For performance-related queries → link to official factsheet only

### Transparency
- Responses must be short, factual, and verifiable
- Every answer must include a source link and last-updated date

---

## 6. User Interface (Minimal)

The UI should include:
- A **welcome message**
- **Three example questions** to guide the user
- A visible **disclaimer**: `"Facts-only. No investment advice."`

---

## 7. Architecture Overview

```
┌──────────────┐     ┌────────────────┐     ┌──────────────────┐
│  User Query  │────▸│  RAG Pipeline  │────▸│  LLM Generation  │
└──────────────┘     │                │     │  (with retrieved  │
                     │  1. Embed query│     │   context)        │
                     │  2. Retrieve   │     └────────┬─────────┘
                     │     chunks     │              │
                     │  3. Re-rank    │              ▼
                     └───────┬────────┘     ┌──────────────────┐
                             │              │  Formatted Answer │
                     ┌───────▼────────┐     │  + Citation       │
                     │ Vector Store   │     │  + Last Updated   │
                     │ (embedded docs)│     └──────────────────┘
                     └────────────────┘
```

**Key components:**
1. **Document Ingestion** — Scrape / load official URLs, chunk, and embed into a vector store
2. **Retrieval** — Semantic search over the vector store for relevant chunks
3. **Generation** — LLM produces a concise, 3-sentence answer grounded in retrieved context
4. **Guardrails** — Refuse advisory queries; enforce citation and format rules

---

## 8. Expected Deliverables

| Deliverable | Details |
|---|---|
| RAG Pipeline | Ingestion, embedding, retrieval, and generation |
| FAQ Chatbot UI | Minimal interface with welcome message, examples, and disclaimer |
| README | Setup instructions, selected AMC/schemes, architecture overview, known limitations |
| Disclaimer | `"Facts-only. No investment advice."` embedded in UI and README |

---

## 9. Success Criteria

- [ ] Accurate retrieval of factual mutual fund information
- [ ] Strict adherence to facts-only responses (no advice)
- [ ] Consistent inclusion of valid source citations
- [ ] Proper refusal of advisory queries with educational links
- [ ] Clean, minimal, and user-friendly interface

---

## 10. Known Risks & Considerations

| Risk | Mitigation |
|---|---|
| Source documents become outdated | Include `last updated` dates; periodic re-ingestion |
| LLM hallucination beyond retrieved context | Strict grounding prompts; limit response to retrieved chunks only |
| Ambiguous queries crossing facts/advice boundary | Conservative refusal policy; err on the side of refusing |
| Corpus gaps (scheme not covered) | Clearly communicate coverage scope to the user |

---

*Derived from [problemstatement.txt](file:///Users/sanjeevjha/Desktop/RAG%20Chatbot/docs/problemstatement.txt)*
