from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .mock_runtime import actor_answer, evaluator, reflector
from .schemas import AttemptTrace, QAExample, ReflectionEntry, RunRecord

@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1
    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0
        for attempt_id in range(1, self.max_attempts + 1):
            answer, tok_act, lat_act = actor_answer(example, attempt_id, self.agent_type, reflection_memory)
            judge, tok_ev, lat_ev = evaluator(example, answer)
            
            step_tokens = tok_act + tok_ev
            step_latency = lat_act + lat_ev
            
            trace = AttemptTrace(attempt_id=attempt_id, answer=answer, score=judge.score, reason=judge.reason, token_estimate=step_tokens, latency_ms=step_latency)
            final_answer = answer
            final_score = judge.score
            if judge.score == 1:
                traces.append(trace)
                break
            
            # TODO: Học viên triển khai logic Reflexion tại đây
            if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
                reflection_entry, tok_ref, lat_ref = reflector(example, attempt_id, judge)
                reflections.append(reflection_entry)
                reflection_memory.append(f"Lesson: {reflection_entry.lesson}\nStrategy: {reflection_entry.next_strategy}")
                trace.token_estimate += tok_ref
                trace.latency_ms += lat_ref
            traces.append(trace)
        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        if final_score == 1:
            failure_mode = "none"
        else:
            reason = traces[-1].reason.lower() if traces else ""
            if "missing" in reason:
                failure_mode = "missing_evidence"
            elif "spurious" in reason:
                failure_mode = "spurious_claims"
            elif "parse" in reason:
                failure_mode = "parse_failed"
            else:
                failure_mode = "wrong_final_answer"
        return RunRecord(qid=example.qid, question=example.question, gold_answer=example.gold_answer, agent_type=self.agent_type, predicted_answer=final_answer, is_correct=bool(final_score), attempts=len(traces), token_estimate=total_tokens, latency_ms=total_latency, failure_mode=failure_mode, reflections=reflections, traces=traces)

class ReActAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(agent_type="react", max_attempts=1)

class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3) -> None:
        super().__init__(agent_type="reflexion", max_attempts=max_attempts)
