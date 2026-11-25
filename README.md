# 🌱 EvoMindAgri: Human-in-the-Loop Governed Episodic Memory for Reliable Small-LLM Agricultural Advisory

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Backend-Flask-lightgrey.svg)](https://flask.palletsprojects.com/)
[![MongoDB](https://img.shields.io/badge/Database-MongoDB-green.svg)](https://www.mongodb.com/)
[![Ollama](https://img.shields.io/badge/Local_LLM-Ollama_(Qwen2.5:3B)-orange.svg)](https://ollama.com/)
[![Status](https://img.shields.io/badge/Research-Benchmark_Verified-brightgreen.svg)](#experimental-achievements)

**EvoMindAgri** is a local-first, privacy-preserving agricultural advisory system designed for small-parameter Large Language Models (`qwen2.5:3b`). Instead of letting unverified user guesses, hypothetical queries, or third-party mentions silently corrupt long-term memory (*context poisoning*), EvoMindAgri introduces a **Human-in-the-Loop (HITL) Governed Episodic Memory Lifecycle** backed by deterministic agricultural NLP, provenance version control, and temporal validity windows.

---

## 🎯 What It Does (The Problem & Solution)

### The Challenge
Deploying cloud LLMs for smallholder farmers in regions like Haryana and Punjab faces steep barriers in connectivity, API cost, and data privacy. However, running lightweight **3B-parameter local models** introduces two critical failure modes:
1. **Context Poisoning:** Standard auto-memory agents blindly save hypothetical questions (*"What if my soil pH was 9.1?"*) or neighbor reports (*"My neighbor's wheat has yellow rust"*) as permanent user facts.
2. **Unsafe Hallucinations & Stale State:** Overwriting historical soil tests without version tracking or treating unverified disease symptoms as confirmed lab diagnoses leads to dangerous fertilizer or pesticide advice.

### The EvoMindAgri Solution
EvoMindAgri separates **conversational fluency** from **state persistence**:
* **Quarantined Memory Proposals:** Candidate farm facts extracted from chat are placed in a `pending` state and **never** injected into the LLM context until explicitly reviewed and approved by the farmer.
* **Third-Party & Hypothetical Filtering:** Symbolic assertion filters block non-personal, hypothetical, and third-party utterances before proposals are even created.
* **Versioned Provenance & Audit Logs:** Updating an existing farm attribute (e.g., soil pH changing from `8.4` $\rightarrow$ `7.3`) archives the prior state in `memory_versions`, increments the version counter, and records an immutable audit trail.
* **Agronomic Temporal Decay (`valid_until`):** Transient biotic reports (pests/disease symptoms) automatically expire after **30 days**, seasonal crop/irrigation records persist for **180 days**, and static soil/farm profiles persist until superseded.
* **Soil-Chemistry & Prescription Guardrails:** Enforces domain safety constraints (e.g., elemental sulfur vs. agricultural lime pH directionality and mandatory verification disclaimers before chemical dosing).

---

## ⚙️ How It Works (System Architecture)

```text
Farmer Utterance
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│ 1. Symbolic Agricultural NLU (services/agri_ner.py)      │
│    • spaCy EntityRuler (9 domain classes, 80+ terms)     │
│    • Priority Intent Router (MEMORY_RECALL override)     │
│    • Regex Measurement Extractor (pH, kg/ha, mm, °C)     │
└──────────────────────────────┬───────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────┐
│ 2. Governed Memory Engine (services/memory_service.py)   │
│    • Direct First-Person Assertion Filter                │
│    • Quarantined Proposal Queue (status: "pending")      │
│    • Farmer Dashboard Gate: [Approve] / [Reject]         │
│    • Version Archival (v_k -> v_{k+1}) & TTL Filtering   │
└──────────────────────────────┬───────────────────────────┘
                               │ (Approved & Active Memories Only)
                               ▼
┌──────────────────────────────────────────────────────────┐
│ 3. Safety-Constrained Inference (services/llm_service.py)│
│    • Local Ollama Runtime (qwen2.5:3b, temp=0.2)         │
│    • Scoped Context (Farmer Memories + General Knowledge)│
│    • Short-Term Dialogue Window + Soil Safety Guardrails │
└──────────────────────────────────────────────────────────┘
```

---

## 🏆 Experimental Achievements

To validate EvoMindAgri against standard conversational memory paradigms, we evaluated three architectural configurations across multi-turn agricultural scenarios covering **cross-session fact recall**, **temporal state updates**, **context poisoning traps**, **unapproved memory isolation**, and **soil-chemistry safety guardrails**:

1. **Stateless Baseline:** Sliding-window conversation history only (no persistent memory).
2. **Un-gated Auto-Memory:** Standard agentic memory that immediately commits every extracted entity without assertion filtering or human approval.
3. **EvoMindAgri (Governed):** Our proposed architecture with assertion filtering, quarantined proposals, HITL approval, and versioned retrieval.

### Ablation Benchmark Results (`qwen2.5:3b` via Ollama)

| Evaluation Metric | Stateless Baseline | Un-gated Auto-Memory | **EvoMindAgri (Governed)** |
| :--- | :---: | :---: | :---: |
| **Overall Task Pass Rate (%)** $\uparrow$ | 61.54% | 46.15% | **84.62%** |
| **Cross-Session Recall & Update Accuracy (%)** $\uparrow$ | 83.33% | 100.00% | **100.00%** |
| **Context Poisoning Rate (%)** $\downarrow$ | 41.67% | 91.67% | **8.33%** |
| **Memory Write Precision (%)** $\uparrow$ | 0.00% | 78.38% | **100.00%** |
| **Memory Write Recall (%)** $\uparrow$ | 0.00% | 100.00% | **100.00%** |
| **Memory Write F1-Score (%)** $\uparrow$ | 0.00% | 87.88% | **100.00%** |
| **Mean End-to-End Latency (ms)** $\downarrow$ | 7,814.26 ms | 7,352.29 ms | **6,585.48 ms** |
| **Mean Prompt Tokens per Turn** $\downarrow$ | 1,265.0 | 1,231.9 | **1,147.7** |

### Key Takeaways
* **+38.47% Higher Task Reliability over Un-gated Memory:** Preventing unverified and third-party entities from polluting the prompt boosted overall pass rate from `46.15%` to `84.62%`.
* **11$\times$ Reduction in Context Poisoning:** Context poisoning dropped from `91.67%` (un-gated auto-memory) to `8.33%` while maintaining `100.0%` precision and recall on valid farmer facts.
* **Lower Compute & Latency Overhead:** Filtering out irrelevant auto-extracted entities reduced average prompt size to `1,147.7` tokens and improved mean response latency to `6.59 s` on local CPU/consumer GPU hardware.

---

## 📂 Repository Structure

```text
EvoMindAgri/
├── app.py                        # Flask web server & REST API endpoints
├── config.py                     # Environment & model configuration
├── database.py                   # MongoDB client & collection definitions
├── requirements.txt              # Python dependencies
├── services/
│   ├── agri_ner.py               # Symbolic spaCy EntityRuler, intent router & regex extractor
│   ├── agri_nlp.py               # Unified NLP analysis wrapper
│   ├── memory_service.py         # HITL proposal queue, versioning, TTL decay & audit logging
│   └── llm_service.py            # Ollama prompt assembly, safety guardrails & telemetry
├── benchmark/
│   ├── dataset_haryana_agri.json # Multi-turn agricultural evaluation benchmark
│   ├── run_benchmark.py          # Automated 3-baseline ablation evaluation runner
│   ├── plot_results.py           # 300-DPI publication chart generator
│   ├── results_summary.json      # Detailed per-case metrics & telemetry logs
│   └── results_table.md          # Formatted ablation comparison table
├── templates/
│   └── index.html                # Responsive Farmer Assistant & Memory Governance UI
└── static/
    ├── css/style.css             # Dashboard styling
    └── js/app.js                 # Frontend state, proposal approval & version history UI
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* **Python 3.10+**
* **MongoDB** (local instance or MongoDB Atlas URI)
* **Ollama** installed locally with `qwen2.5:3b` pulled:
  ```bash
  ollama pull qwen2.5:3b
  ```

### 2. Installation
```bash
# Clone the repository and enter the project directory
cd EvoMindAgri

# Create and activate a virtual environment
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory:
```env
FLASK_SECRET_KEY=replace-with-a-strong-random-secret-key
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=evomindagri
OLLAMA_MODEL=qwen2.5:3b
```

### 4. Run the Application
```bash
python app.py
```
Open `http://127.0.0.1:5000` in your browser to interact with the assistant, inspect extracted agricultural entities, and approve or reject proposed farm memories.

---

## 🧪 Reproducing the Research Benchmark

To reproduce the ablation study results in `benchmark/results_table.md`:

```bash
# Ensure MongoDB and Ollama are running, then execute:
python benchmark/run_benchmark.py

# Generate high-resolution comparison figures:
python benchmark/plot_results.py
```
*(Note: The benchmark suite uses isolated synthetic `owner_id` prefixes and automatically cleans up all test documents from MongoDB upon completion.)*

---

## ⚠️ Disclaimer & Scope
* EvoMindAgri is a research prototype focused initially on wheat and mustard agronomy in Haryana, India.
* Agricultural recommendations—particularly chemical, pesticide, and soil-amendment dosages—are intended for decision support and require verification by qualified agronomists or official agricultural extension guidelines.