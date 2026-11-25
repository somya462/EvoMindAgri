# EvoMindAgri Ablation Benchmark Results

| Metric | Stateless Baseline | Un-gated Auto-Memory | EvoMindAgri (Governed) |
| :--- | :---: | :---: | :---: |
| Overall Task Pass Rate (%) | 64.0 | 56.0 | 100.0 |
| Cross-Session Recall & Update Accuracy (%) | 80.0 | 100.0 | 100.0 |
| Context Poisoning Rate (% $\downarrow$) | 31.82 | 86.36 | 0.0 |
| Memory Write Precision (%) | 0.0 | 78.95 | 96.77 |
| Memory Write Recall (%) | 0.0 | 96.77 | 96.77 |
| Memory Write F1-Score (%) | 0.0 | 86.96 | 96.77 |
| Mean End-to-End Latency (ms $\downarrow$) | 7859.38 | 7866.23 | 7694.48 |
| Mean Prompt Tokens ($\downarrow$) | 1274.2 | 1246.4 | 1165.3 |
