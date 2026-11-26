# EvoMindAgri: Deterministic Entity-Governed Memory Architecture for Longitudinal Agricultural Advisory Agents

**EvoMindAgri** is a neuro-symbolic, deterministic memory governance architecture designed to prevent conversational context poisoning and input token inflation in multi-turn Large Language Model (LLM) agricultural advisory assistants.

By decoupling natural-language response generation from persistent state management, EvoMindAgri interposes an auditable write-time symbolic verification gate built on **spaCy `EntityRuler`**, curated agronomic domain ontologies, compiled regular-expression quantitative extractors, and versioned state conflict resolution.

---

## Core Architecture

1. **Assertion & Hypothesis Screening (`services/memory_service.py`):** Uses predefined lexical exclusion patterns to filter selected hypothetical, negated, and third-party references alongside first-person ownership indicators to identify farmer-specific declarative assertions.
2. **Deterministic Agronomic Entity Extraction (`services/agri_ner.py`):** Uses spaCy (`>= 3.7.0`) `EntityRuler` with curated agronomic dictionaries covering crops, cultivars, growth stages, pests, pathogens, agro-inputs, soil types, and regional agricultural locations.
3. **Regex Quantitative Extractors (`services/agri_ner.py`):** Extracts structured numeric measurements across four regex classes (`pH` values, area-based fertilizer quantities in `kg/ha`, spatial/rainfall depths in `mm`/`cm`/`inches`, and ambient/soil temperatures in `°C` plus percentages `%`) and maps extracted entities onto canonical schema fields (`crop_*`, `farm_location`, `soil_type`, `soil_ph`, `farm_area`, `irrigation_method`, `growth_stage`, `reported_pest_*`, and `reported_symptom_*`).
4. **Schema-Based Memory Governance Gate & Versioning (`services/memory_service.py`):** Validates assertion status and canonical schema mapping before creating pending proposals, and archives superseded values as read-only historical versions (`memory_versions`) upon approval.
5. **Canonical State Serialization (`services/llm_service.py`):** Serializes only approved active records into a compact JSON context block prepended to the user prompt wrapper, bounding input token growth across turns.

---

## Controlled Ablation Benchmark Results (25 Scenarios)

Evaluated locally on a 12th Gen Intel Core i5-12450H CPU (16 GB RAM, CPU-only inference) using **Ollama** (`qwen2.5:3b`, $T = 0.2$, `num_ctx = 4096`) across 25 multi-turn scenarios stratified into five diagnostic categories (`A01`–`E05`):

| Metric | Stateless Baseline | Un-gated Auto-Memory | EvoMindAgri (Governed) |
| :--- | :---: | :---: | :---: |
| **Overall Task Pass Rate (%)** | 76.0 (19/25) | 56.0 (14/25) | **96.0 (24/25)** |
| **Recall & Temporal Update Pass Rate (%)** | **100.0 (10/10)** | 90.0 (9/10) | **100.0 (10/10)** |
| **Response-Level Lexical Leakage Rate (% $\downarrow$)** | 31.82 (7/22) | 86.36 (19/22) | **4.55 (1/22)** |
| **Unauthorized Memory Commits in Cat. C–D ($\downarrow$)** | N/A | 25 | **0** |
| **Candidate Proposal Precision (%)** | N/A (0/0) | 78.95 (60/76) | **96.77 (60/62)** |
| **Candidate Proposal Recall (%)** | 0.0 (0/62) | **96.77 (60/62)** | **96.77 (60/62)** |
| **Candidate Proposal F1-Score (%)** | 0.0 | 86.96 | **96.77** |
| **Committed Write Event Precision (%)** | N/A (0/0) | 62.32 (43/69) | **98.00 (49/50)** |
| **Committed Write Event Recall (%)** | 0.0 (0/50) | 86.00 (43/50) | **98.00 (49/50)** |
| **Committed Write Event F1-Score (%)** | 0.0 | 72.27 | **98.00** |
| **Archived State Versions (Count)** | 0 | 0 | **6** |
| **Mean Per-Turn End-to-End Latency (ms $\downarrow$)** | $7247.68 \pm 2005.12$ | $7589.29 \pm 1951.24$ | **$7672.20 \pm 1559.78$** |
| **Mean Input Prompt Tokens per Turn ($\downarrow$)** | $1260.8 \pm 115.6$ | $1241.0 \pm 72.8$ | **$1162.7 \pm 167.8$** |

### Key Benchmark Takeaways
* **94.74% Reduction in Response-Level Lexical Leakage (`1/22`, `4.55%` vs. `19/22`, `86.36%`):** Across all 22 counterfactual poisoning and unapproved-action exclusion probes in Categories C and D, `evomind_governed` had only 1 response-level lexical probe violation (in `C05`, where the model repeated a counterfactual term in its advisory explanation without storing it in memory), compared to `86.36%` for `ungated_auto` and `31.82%` for `stateless`.
* **Zero Unauthorized Persistent Commits in Categories C–D (`0` vs. `25`):** Across Categories C and D combined, `evomind_governed` committed **0** unauthorized records to persistent storage (quarantining `D03`'s single false-positive proposal in pending state when `approve_proposals` is false), compared to **25** unauthorized persistent commits in `ungated_auto`.
* **Event-Level Two-Stage Memory Fidelity (`96.77%` Proposal F1 & `98.00%` Committed Write Event F1):** Against 62 gold candidate proposal events, `evomind_governed` achieved `60 TP, 2 FP, 2 FN` (`96.77%` F1); across all 50 individual oracle-approved commit events (including the 6 superseded versions in `B01`–`B05`), it achieved `49 TP, 1 FP, 1 FN` (`98.00%` F1, with the single committed false positive occurring in `E04`).
* **Lower Input Token Consumption (`1,162.7` tokens/turn):** Serializing compact canonical tuples reduced mean input prompt tokens by **7.78%** vs. `stateless` (`1,260.8`) and **6.31%** vs. `ungated_auto` (`1,241.0`) with comparable per-turn latency.

---

## Repository Structure

```text
EvoMindAgri/
├── benchmark/
│   ├── dataset_haryana_agri.json      # 25 multi-turn scenarios & gold annotations
│   ├── run_benchmark.py               # Automated ablation evaluation harness
│   ├── plot_results.py                # 300-DPI publication figure generator
│   ├── results_summary.json           # Complete raw telemetry & per-case logs
│   ├── results_table.md               # Markdown summary table of benchmark metrics
│   ├── fig1_ablation_performance.png  # Ablation performance comparison chart
│   └── fig2_efficiency_tradeoff.png   # Latency & input token efficiency chart
├── services/
│   ├── agri_ner.py                    # spaCy EntityRuler, ontologies & regex extractors
│   ├── memory_service.py              # Deterministic write gate, versioning & baselines
│   └── llm_service.py                 # Ollama inference wrapper & token telemetry
├── database.py                        # MongoDB collections & connection setup
├── requirements.txt                   # Python dependencies
├── .env.example                       # Environment configuration template
└── README.md                          # Project documentation
```

---

## Reproducing the Benchmark

```bash
git clone [https://github.com/somya462/EvoMindAgri.git](https://github.com/somya462/EvoMindAgri.git)
cd EvoMindAgri
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
ollama pull qwen2.5:3b
python benchmark/run_benchmark.py
python benchmark/plot_results.py
```