# EvoMindAgri Ablation Benchmark Results

| Metric | Stateless Baseline | Un-gated Auto-Memory | EvoMindAgri (Governed) |
| :--- | :---: | :---: | :---: |
| Overall Task Pass Rate (%) | 76.0 | 56.0 | **96.0** |
| Recall & Temporal Update Pass Rate (%) | 100.0 | 90.0 | **100.0** |
| Response-Level Lexical Leakage Rate (% $\downarrow$) | 31.82 | 86.36 | **4.55** |
| Unauthorized Memory Commits in Cat. C–D ($\downarrow$) | N/A | 25 | **0** |
| Candidate Proposal F1-Score (%) | 0.0 | 86.96 | **96.77** |
| Committed Memory Write Event F1-Score (%) | 0.0 | 72.27 | **98.0** |
| Archived State Versions (Count) | 0 | 0 | **6** |
| Mean Per-Turn End-to-End Latency (ms $\downarrow$) | 7247.68 | 7589.29 | **7672.2** |
| Mean Input Prompt Tokens per Turn ($\downarrow$) | 1260.8 | 1241.0 | **1162.7** |
