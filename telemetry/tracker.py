import os
import json
from pathlib import Path
from datetime import datetime
import threading

_telemetry_lock = threading.Lock()  # Lock for thread-safe telemetry operations

#https://ai.google.dev/gemini-api/docs/models 
PRICING = {
    # current stable Gemini 3 series
    "gemini/gemini-3.7-flash": {"input_per_million": 0.10,  "output_per_million": 0.40},
    "gemini/gemini-3.6-flash": {"input_per_million": 0.10,  "output_per_million": 0.40},
    "gemini/gemini-3.5-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    # older 2.5 family (still listed but restricted)
    "gemini/gemini-2.5-pro":   {"input_per_million": 1.25,  "output_per_million": 10.00},
    "gemini/gemini-2.5-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
}


#pricing is quoted per million tokens, but actual usage is a few thousand tokens per call, so we need to scale down proportionally.

def calculate_cost(model, input_tokens, output_tokens):
    if model not in PRICING:
        return None

    prices = PRICING[model]
    input_cost = (input_tokens / 1_000_000) * prices["input_per_million"]
    output_cost = (output_tokens / 1_000_000) * prices["output_per_million"]
    total_cost = input_cost + output_cost

    return total_cost

def load_telemetry(telemetry_file):
    if os.path.exists(telemetry_file):
        with open(telemetry_file, 'r') as f:
            try:
                return json.load(f).get("calls", [])
            except json.JSONDecodeError:
                return []
    return []

def save_telemetry(telemetry_file, calls):
    path = Path(telemetry_file).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(telemetry_file, 'w') as f:
        json.dump({"calls": calls}, f, indent=4)

def record_call(telemetry_file,run_id, agent_name, model, input_tokens, output_tokens, start_time=None, end_time=None):
    with _telemetry_lock:  # Ensure thread-safe access to telemetry
        calls = load_telemetry(telemetry_file)
        cost = calculate_cost(model, input_tokens, output_tokens)
        new_call = {
            "run_id": run_id,                        #this is a uuid, 4 calls from the same document-processing run all share one run_id and group together, while a second run's single call stays properly separate.
            "timestamp": datetime.now().isoformat(),
            "agent_name": agent_name,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "start_time": start_time,   #captured before the LLM call starts
            "end_time": end_time        #captured after the LLM call returns
        }
        calls.append(new_call)  # Append the new call with the run_id
        save_telemetry(telemetry_file, calls)

def summarize_run(telemetry_file, run_id):
    all_calls = load_telemetry(telemetry_file)
    run_calls = []

    for call in all_calls:
        if call["run_id"] == run_id:
            run_calls.append(call)

    total_input_tokens = sum(call["input_tokens"] for call in run_calls)
    total_output_tokens = sum(call["output_tokens"] for call in run_calls) 

    total_cost = sum(call["cost"] for call in run_calls if call["cost"] is not None)

    by_agent = {}
    for call in run_calls:
        agent = call["agent_name"]
        if agent not in by_agent:
            by_agent[agent] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0
            }
        by_agent[agent]["input_tokens"] += call["input_tokens"]
        by_agent[agent]["output_tokens"] += call["output_tokens"]
        if call["cost"] is not None:
            by_agent[agent]["cost"] += call["cost"]

    return {
        "run_id": run_id,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cost": total_cost,
        "calls": run_calls,
        "by_agent": by_agent
    }       