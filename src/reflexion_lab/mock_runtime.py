import os
import json
import time
from openai import OpenAI
from pydantic import ValidationError
from .schemas import QAExample, JudgeResult, ReflectionEntry
from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .utils import normalize_answer

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY", "dummy_key"),
)

MODEL = "deepseek/deepseek-v4-flash"

def actor_answer(example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> tuple[str, int, int]:
    context_str = "\n\n".join([f"[{c.title}]\n{c.text}" for c in example.context])
    user_prompt = f"Question: {example.question}\n\nContext:\n{context_str}"
    
    if reflection_memory:
        user_prompt += "\n\nPrevious Lessons & Strategies:\n" + "\n".join(reflection_memory)
        
    start_time = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ACTOR_SYSTEM},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0
    )
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    tokens = getattr(response.usage, 'total_tokens', 0) if response.usage else 0
    return response.choices[0].message.content.strip(), tokens, latency_ms

def evaluator(example: QAExample, answer: str) -> tuple[JudgeResult, int, int]:
    if normalize_answer(example.gold_answer) == normalize_answer(answer):
        return JudgeResult(score=1, reason="Exact match", missing_evidence=[], spurious_claims=[]), 0, 0
        
    schema_str = json.dumps(JudgeResult.model_json_schema(), indent=2)
    sys_prompt = EVALUATOR_SYSTEM + f"\n\nExpected JSON Schema:\n{schema_str}\n\nIMPORTANT: Return a JSON object with your actual evaluation data. DO NOT output the schema itself."
    user_prompt = f"Question: {example.question}\nGold Answer: {example.gold_answer}\nPredicted Answer: {answer}"
    
    start_time = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    tokens = getattr(response.usage, 'total_tokens', 0) if response.usage else 0
    content = response.choices[0].message.content
    try:
        return JudgeResult.model_validate_json(content), tokens, latency_ms
    except Exception:
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return JudgeResult.model_validate_json(match.group(0)), tokens, latency_ms
        return JudgeResult(score=0, reason="Parse failed", missing_evidence=[], spurious_claims=[]), tokens, latency_ms

def reflector(example: QAExample, attempt_id: int, judge: JudgeResult) -> tuple[ReflectionEntry, int, int]:
    schema_str = json.dumps(ReflectionEntry.model_json_schema(), indent=2)
    sys_prompt = REFLECTOR_SYSTEM + f"\n\nExpected JSON Schema:\n{schema_str}\n\nIMPORTANT: Return a JSON object with your actual reflection data. DO NOT output the schema itself."
    user_prompt = f"Question: {example.question}\nFailed Attempt Reason: {judge.reason}\nMissing Evidence: {judge.missing_evidence}\nSpurious Claims: {judge.spurious_claims}"
    
    start_time = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    tokens = getattr(response.usage, 'total_tokens', 0) if response.usage else 0
    content = response.choices[0].message.content
    try:
        entry = ReflectionEntry.model_validate_json(content)
        entry.attempt_id = attempt_id
        return entry, tokens, latency_ms
    except Exception:
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            entry = ReflectionEntry.model_validate_json(match.group(0))
            entry.attempt_id = attempt_id
            return entry, tokens, latency_ms
        return ReflectionEntry(attempt_id=attempt_id, failure_reason="Parse error", lesson="Error", next_strategy="Error"), tokens, latency_ms
