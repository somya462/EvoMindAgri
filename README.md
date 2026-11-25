# EvoMindAgri: Deterministic Entity-Governed Memory Architecture for Longitudinal Agricultural Advisory Agents

**EvoMindAgri** is a neuro-symbolic, deterministic memory governance architecture designed to prevent conversational context poisoning and input token inflation in multi-turn Large Language Model (LLM) agricultural advisory assistants.

By decoupling natural-language response generation from persistent state management, EvoMindAgri interposes an auditable write-time symbolic verification gate built on **spaCy `EntityRuler`**, curated agronomic domain ontologies, compiled regular-expression quantitative extractors, and versioned state conflict resolution.

---

## Research Paper Scope vs. Extended Application Features

> **Research Paper Scope:** The accompanying research manuscript (*"EvoMindAgri: A Deterministic Entity-Governed Memory Architecture for Reliable Longitudinal Agricultural Advisory Agents"*) evaluates the deterministic write-time memory-governance pipeline using a controlled 25-scenario multi-turn agricultural benchmark (`benchmark/dataset_haryana_agri.json`). During benchmark execution, candidate memory proposals passing the deterministic governance gate are committed via the automated benchmark oracle (`approve_proposals: true` for valid declarative turns) so that the symbolic write gate and oracle-approved persistence lifecycle are evaluated repeatably.
>
> **Extended Application Capabilities:** Beyond the core deterministic gate evaluated in the manuscript, this repository also includes broader application-level capabilities—including an interactive pending proposal queue (`memory_proposals`), farmer approval/rejection endpoints (`approve_memory_proposal`), temporal validity metadata, and user-facing interface components. These extended features form part of the end-to-end application implementation and should not be interpreted as independently evaluated human-usability claims of the reported benchmark.

---

## Core Architecture

1. **Intent & Hypothesis Screening (`services/memory_service.py`):** Distinguishes declarative field updates (e.g., *"I applied 50 kg/ha of urea yesterday"*) from counterfactual queries (*"What if I applied..."*), negations, and unapproved plans.
2. **Deterministic Agronomic Entity Extraction (`services/agri_ner.py`):** Uses spaCy (`>= 3.7.0`) `EntityRuler` with curated agronomic dictionaries covering crops, cultivars, growth stages, pests, pathogens, agro-inputs, soil parameters, and Indian agricultural locations.
3. **Regex Quantitative & Measurement Extractors (`services/agri_ner.py`):** Extracts structured numeric measurements (`pH`, area-based fertilizer rates in `kg/ha`, `g/acre`, `q/ha`, `tons/ha`, depth/rainfall in `mm`, `cm`, `inch`, temperature in `°C`/`°F`, and percentages `%`) and maps them onto canonical memory schema fields (`crop`, `location`, `soil_type`, `disease`, `pest`, `irrigation`, `growth_stage`, `farm_area`, `soil_ph`).
4. **Schema-Based Memory Governance Gate (`services/memory_service.py`):** Validates declarative assertion status, ontology membership, and schema-encoded numeric bounds (e.g., `soil_ph` within `[0.0, 14.0]`) before generating candidate memory proposals, preserving superseded values as read-only historical versions (`memory_versions`) upon approval.
5. **Canonical State Serialization (`services/llm_service.py`):** Serializes only approved active records into a compact JSON context block prepended to the user prompt wrapper, bounding input token growth across turns.

---

## Controlled Ablation Benchmark Results (25 Scenarios)

Evaluated locally on a 12th Gen Intel Core i5-12450H CPU (16 GB RAM, CPU-only inference) using **Ollama** (`qwen2.5:3b`, $T = 0.2$, `num_ctx = 4096`) across 25 multi-turn scenarios stratified into five diagnostic categories (`A01`–`E05`):

| Metric | Stateless Baseline | Un-gated Auto-Memory | EvoMindAgri (Governed) |
| :--- | :---: | :---: | :---: |
| **Overall Task Pass Rate (%)** | 88.0 (22/25) | 56.0 (14/25) | **96.0 (24/25)** |
| **Recall & Temporal Update Pass Rate (%)** | **100.0 (10/10)** | 90.0 (9/10) | **100.0 (10/10)** |
| **Response-Level Lexical Leakage Rate (% $\downarrow$)** | 18.18 (4/22) | 81.82 (18/22) | **0.0 (0/22)** |
| **Unauthorized Memory Commits in Cat. C–D ($\downarrow$)** | N/A | 25 | **0** |
| **Candidate Proposal Precision (%)** | N/A (0/0) | 78.95 (60/76) | **96.77 (60/62)** |
| **Candidate Proposal Recall (%)** | 0.0 (0/62) | **96.77 (60/62)** | **96.77 (60/62)** |
| **Candidate Proposal F1-Score (%)** | 0.0 | 86.96 | **96.77** |
| **Committed Memory Write Precision (%)** | N/A (0/0) | 62.32 (43/69) | **97.73 (43/44)** |
| **Committed Memory Write Recall (%)** | 0.0 (0/44) | **97.73 (43/44)** | **97.73 (43/44)** |
| **Committed Memory Write F1-Score (%)** | 0.0 | 76.11 | **97.73** |
| **Archived State Versions (Count)** | 0 | 0 | **6** |
| **Mean Per-Turn End-to-End Latency (ms $\downarrow$)** | $7403.51 \pm 2816.71$ | $7686.90 \pm 1919.16$ | **$7322.01 \pm 1824.22$** |
| **Mean Input Prompt Tokens per Turn ($\downarrow$)** | $1263.2 \pm 107.7$ | $1240.4 \pm 72.1$ | **$1164.3 \pm 167.2$** |

### Key Benchmark Takeaways
* **Zero Response-Level Lexical Leakage (`0/22`, `0.0%`):** Across all 22 counterfactual poisoning and unapproved-action exclusion probes in Categories C and D, `evomind_governed` recorded zero lexical leakage in generated responses (vs. `81.82%` for `ungated_auto` and `18.18%` for `stateless`).
* **Zero Unauthorized Persistent Commits in Categories C–D (`0` vs. `25`):** Across Categories C and D combined, `evomind_governed` committed **0** unauthorized records to `memories_collection` (quarantining `D03`'s single false-positive proposal in pending state when `approve_proposals` is false), compared to **25** unauthorized persistent writes in `ungated_auto`.
* **Two-Stage Memory Fidelity (`96.77%` Proposal F1 & `97.73%` Committed Write F1):** Against 62 gold candidate proposal events, `evomind_governed` achieved `60 TP, 2 FP, 2 FN` (`96.77%` F1); against 44 oracle-approved gold persistent-memory commits, it achieved `43 TP, 1 FP, 1 FN` (`97.73%` F1, with the single committed false positive occurring in `E04`) while archiving `6` superseded state versions (`B01`–`B05`).
* **Lower Input Token Consumption (`1,164.3` tokens/turn):** Serializing compact canonical tuples reduced mean input prompt tokens by **7.83%** vs. `stateless` (`1,263.2`) and **6.14%** vs. `ungated_auto` (`1,240.4`) with comparable per-turn latency.

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

---

## Citation

```bibtex
@article{somya2026evomindagri,
  title={EvoMindAgri: A Deterministic Entity-Governed Memory Architecture for Reliable Longitudinal Agricultural Advisory Agents},
  author={Somya},
  journal={Computers and Electronics in Agriculture},
  year={2026},
  note={Under review}
}
```