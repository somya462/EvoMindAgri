# EvoMindAgri: Deterministic Entity-Governed Memory Architecture for Longitudinal Agricultural Advisory Agents

**EvoMindAgri** is a neuro-symbolic, deterministic memory governance architecture designed to prevent conversational context poisoning and input token inflation in multi-turn Large Language Model (LLM) agricultural advisory assistants.

By decoupling natural-language response generation from persistent state management, EvoMindAgri interposes an auditable write-time symbolic verification gate built on **spaCy `EntityRuler`**, curated agronomic domain ontologies, compiled regular-expression quantitative extractors, and versioned state conflict resolution.

---

## Research Paper Scope vs. Broader Application Features

> **Research Paper Scope:** The accompanying research manuscript (*"EvoMindAgri: A Deterministic Entity-Governed Memory Architecture for Reliable Longitudinal Agricultural Advisory Agents"*) evaluates the deterministic write-time memory-governance pipeline using a controlled 25-scenario multi-turn agricultural benchmark (`benchmark/dataset_haryana_agri.json`). During benchmark execution, candidate memory proposals passing the deterministic governance gate are committed via the automated benchmark oracle (`approve_proposals: true` for valid declarative turns) so that the symbolic write gate is isolated and evaluated deterministically.
>
> **Extended Application Capabilities:** Beyond the core deterministic gate evaluated in the manuscript, this repository also includes broader application-level capabilities—including an interactive human-in-the-loop pending proposal queue (`memory_proposals`), explicit farmer approval/rejection workflows (`approve_memory_proposal`), temporal validity windows, and user-facing interface components. These extended features form part of the end-to-end application implementation and should not be interpreted as independently evaluated experimental claims of the reported benchmark.

---

## Core Architecture

1. **Intent & Hypothesis Screening:** Distinguishes declarative field updates (e.g., *"I applied 50 kg/ha of urea yesterday"*) from counterfactual queries (*"What if I applied..."*), negations, and unapproved plans.
2. **Deterministic Agronomic Entity Extraction (`services/agri_ner.py`):** Uses spaCy (`>= 3.7.0`) `EntityRuler` with curated agronomic dictionaries covering five core grouped ontologies (`CROP` & `CULTIVAR`, `GROWTH_STAGE`, `PEST_PATHOGEN`, `AGRO_INPUT`, and `SOIL_ENV_PARAM`).
3. **Regex Measurement & Dosage Extractors:** Parses exact quantitative rates and physical units ($\text{kg ha}^{-1}$, $\text{mL L}^{-1}$, $\text{g L}^{-1}$, $\text{dS m}^{-1}$, $\text{pH}$, $\text{DAS}$, $\text{DAT}$, $\text{mm}$, plot area) and binds them to governing entities.
4. **Schema-Based Memory Governance Gate (`services/memory_service.py`):** Validates declarative assertion status, ontology membership, and schema-encoded measurement-unit compatibility before authorizing persistent writes, preserving superseded values as read-only historical versions (`memory_versions`).
5. **Canonical State Serialization (`services/llm_service.py`):** Serializes only structurally validated active records into a compact JSON context block prepended to the user prompt wrapper, bounding input token growth across turns.

---

## Controlled Ablation Benchmark Results (25 Scenarios)

Evaluated locally on a 12th Gen Intel Core i5-12450H CPU (16 GB RAM, CPU-only inference) using **Ollama** (`qwen2.5:3b`, $T = 0.2$, `num_ctx = 4096`) across 25 multi-turn scenarios stratified into five diagnostic categories (`A01`–`E05`):

| Metric | Stateless Baseline | Un-gated Auto-Memory | EvoMindAgri (Governed) |
| :--- | :---: | :---: | :---: |
| **Overall Task Pass Rate (%)** | 64.0 (16/25) | 56.0 (14/25) | **100.0 (25/25)** |
| **Recall & Temporal Update Pass Rate (%)** | 80.0 (8/10) | **100.0 (10/10)** | **100.0 (10/10)** |
| **Response-Level Lexical Leakage Rate (% $\downarrow$)** | 31.82 (7/22) | 86.36 (19/22) | **0.0 (0/22)** |
| **Unauthorized Memory Writes in Cat. C–D ($\downarrow$)** | N/A | 15 | **1** |
| **Memory Write Precision (%)** | N/A (0/0) | 78.95 (60/76) | **96.77 (60/62)** |
| **Memory Write Recall (%)** | 0.0 (0/62) | **96.77 (60/62)** | **96.77 (60/62)** |
| **Memory Write F1-Score (%)** | 0.0 | 86.96 | **96.77** |
| **Archived State Versions (Count)** | 0 | 0 | **6** |
| **Mean Per-Turn End-to-End Latency (ms $\downarrow$)** | $7859 \pm 3129$ | $7866 \pm 2289$ | **$7694 \pm 1833$** |
| **Mean Input Prompt Tokens per Turn ($\downarrow$)** | $1274.2 \pm 105.8$ | $1246.4 \pm 86.6$ | **$1165.3 \pm 167.2$** |

### Key Benchmark Takeaways
* **Zero Response-Level Lexical Leakage (`0/22`, `0.0%`):** Across all 22 counterfactual poisoning and unapproved-action exclusion probes in Categories C and D, `evomind_governed` recorded zero lexical leakage in generated responses (vs. `86.36%` for `ungated_auto` and `31.82%` for `stateless`).
* **93.33% Reduction in Unauthorized Category C–D Memory Writes:** Across Categories C and D combined, `evomind_governed` recorded only **1** unauthorized persistent-memory write (in `D03`, with zero unauthorized writes in Category C) compared to **15** for `ungated_auto`.
* **High Write Classification Fidelity (`96.77%` F1):** Against all 62 gold write events across the 25 scenarios, `evomind_governed` achieved `60 TP`, `2 FP`, and `2 FN` (`96.77%` precision, `96.77%` recall, `96.77%` F1-score) while archiving `6` superseded state versions during temporal updates (`B01`–`B05`).
* **Lower Input Token Consumption (`1,165.3` tokens/turn):** Serializing compact canonical tuples reduced mean input prompt tokens by **8.55%** vs. `stateless` (`1,274.2`) and **6.51%** vs. `ungated_auto` (`1,246.4`) with comparable per-turn latency.

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

### 1. Prerequisites
* **Python:** `3.12+`
* **MongoDB:** Running locally (`mongodb://localhost:27017`)
* **Ollama:** Installed locally with the `qwen2.5:3b` model pulled:
  ```bash
  ollama pull qwen2.5:3b
  ```

### 2. Installation
```bash
git clone [https://github.com/somya462/EvoMindAgri.git](https://github.com/somya462/EvoMindAgri.git)
cd EvoMindAgri
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 3. Run the Ablation Suite & Regenerate Figures
```bash
python benchmark/run_benchmark.py
python benchmark/plot_results.py
```
This executes all 25 scenarios across `stateless`, `ungated_auto`, and `evomind_governed` (75 multi-turn runs), writes updated logs to `benchmark/results_summary.json` and `benchmark/results_table.md`, and regenerates the 300-DPI charts.

---

## Citation

If you use this codebase or benchmark dataset in your research, please cite:

```bibtex
@article{somya2026evomindagri,
  title={EvoMindAgri: A Deterministic Entity-Governed Memory Architecture for Reliable Longitudinal Agricultural Advisory Agents},
  author={Somya},
  journal={Computers and Electronics in Agriculture},
  year={2026},
  note={Under review}
}
```