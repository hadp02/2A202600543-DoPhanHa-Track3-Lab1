# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_combined_50.json
- Mode: mock
- Records: 100
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.94 | 0.98 | 0.04 |
| Avg attempts | 1 | 1.12 | 0.12 |
| Avg token estimate | 1927.78 | 2306.18 | 378.4 |
| Avg latency (ms) | 9547.32 | 15522.36 | 5975.04 |

## Failure modes
```json
{
  "wrong_final_answer": 4
}
```

## Extensions implemented
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding

## Discussion
Reflexion helps when the first attempt stops after the first hop or drifts to a wrong second-hop entity. The tradeoff is higher attempts, token cost, and latency. In a real report, students should explain when the reflection memory was useful, which failure modes remained, and whether evaluator quality limited gains.
