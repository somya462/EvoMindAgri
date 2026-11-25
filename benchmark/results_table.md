# EvoMindAgri Ablation Benchmark Results

| Metric | Stateless Baseline | Un-gated Auto-Memory | EvoMindAgri (Governed) |
| :--- | :---: | :---: | :---: |
| Overall Task Pass Rate (%) | 88.0 (22/25) | 56.0 (14/25) | **96.0 (24/25)** |
| Recall & Temporal Update Pass Rate (%) | **100.0 (10/10)** | 90.0 (9/10) | **100.0 (10/10)** |
| Response-Level Lexical Leakage Rate (% $\downarrow$) | 18.18 (4/22) | 81.82 (18/22) | **0.0 (0/22)** |
| Unauthorized Memory Commits in Cat. C–D ($\downarrow$) | N/A | 25 | **0** |
| Candidate Proposal Precision (%) | N/A (0/0) | 78.95 (60/76) | **96.77 (60/62)** |
| Candidate Proposal Recall (%) | 0.0 (0/62) | **96.77 (60/62)** | **96.77 (60/62)** |
| Candidate Proposal F1-Score (%) | 0.0 | 86.96 | **96.77** |
| Committed Memory Write Precision (%) | N/A (0/0) | 62.32 (43/69) | **97.73 (43/44)** |
| Committed Memory Write Recall (%) | 0.0 (0/44) | **97.73 (43/44)** | **97.73 (43/44)** |
| Committed Memory Write F1-Score (%) | 0.0 | 76.11 | **97.73** |
| Archived State Versions (Count) | 0 | 0 | **6** |
| Mean Per-Turn End-to-End Latency (ms $\downarrow$) | $7403.51 \pm 2816.71$ | $7686.90 \pm 1919.16$ | **$7322.01 \pm 1824.22$** |
| Mean Input Prompt Tokens per Turn ($\downarrow$) | $1263.2 \pm 107.7$ | $1240.4 \pm 72.1$ | **$1164.3 \pm 167.2$** |