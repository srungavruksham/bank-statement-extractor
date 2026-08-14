
import os
import json
from pathlib import Path
from datetime import datetime

def load_episodic_memory(memory_file: str) -> list:
    if os.path.exists(memory_file):
        with open(memory_file, 'r') as f:
            try:
                return json.load(f).get("learnings", [])
            except json.JSONDecodeError:
                return []

    return []

def save_episodic_memory(memory_file: str, learnings: list):
    path = Path(memory_file).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(memory_file, 'w') as f:
        json.dump({"learnings": learnings}, f, indent=4)


def add_episodic_entry(memory_file, source, mistake_description, correction_rule, confidence, caught_by="validator", human_confirmed=False):
    learnings = load_episodic_memory(memory_file) # load what we have already

    new_entry = {
        "source": source,
        "mistake_description": mistake_description,
        "correction_rule": correction_rule,
        "confidence": confidence,
        "caught_by": caught_by,             #wh0 caught this mistake validator or human
        "human_confirmed": human_confirmed, # True -> once a human approves this correction
        "timestamp": datetime.now().isoformat()
    }

    learnings.append(new_entry)                     # add new entry to the list
    save_episodic_memory(memory_file, learnings)    # save the new learning to the episodic file 

def mark_correction_confirmed(memory_file, source, correction_rule):
    # a human approved output that contained this correction, so bump it from
    # machine-asserted to human-confirmed. matches on source + normalized rule.
    learnings = load_episodic_memory(memory_file)
    for entry in learnings:
        if entry["source"] == source and normalize(entry.get("correction_rule", "")) == normalize(correction_rule or ""):
            entry["human_confirmed"] = True
    save_episodic_memory(memory_file, learnings)

def load_semantic_memory(memory_file: str) -> list:
    if os.path.exists(memory_file):
        with open(memory_file, 'r') as f:
            try:  
                return json.load(f).get("rules", [])
            except json.JSONDecodeError:
                return []
    return []    


def save_semantic_memory(memory_file: str, memory_data: list):
    path = Path(memory_file).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(memory_file, 'w') as f:
        json.dump({"rules": memory_data}, f, indent=4)

def normalize(text): 
    return " ".join(text.lower().split())        

def check_for_promotion(episodic_file, semantic_file, threshold = 2):
    episodic_entries = load_episodic_memory(episodic_file)
    semantic_rules = load_semantic_memory(semantic_file)

    # Count occurrences of each mistake description in episodic memory
    counts = {}
    for entry in episodic_entries:
        key = (entry["source"], normalize(entry["correction_rule"]))  
        counts[key] = counts.get(key, 0) + 1

    # Promote rules that meet the threshold to semantic memory
    for (source, normalized_rule), count in counts.items():
        if count >= threshold:
            # Check if this rule already exists in semantic memory
            if not any(rule["source"] == source and normalize(rule["correction_rule"]) == normalized_rule for rule in semantic_rules):  #does semantic_rules already contain an entry matching
                # add to semantic memory
                semantic_rules.append({
                    "source": source,
                    "correction_rule": normalized_rule,
                    "promoted_from_episodic": True,
                    "timestamp": datetime.now().isoformat()
                })

    save_semantic_memory(semantic_file, semantic_rules)
    return semantic_rules  

def format_memory_for_prompt(source , episodic_file,semantic_file):
    semantic_rules = load_semantic_memory(semantic_file)   

    matching_semantic = []

    # Find all semantic rules that match the given source
    for rule in semantic_rules:
        if rule['source'] == source:
            matching_semantic.append(rule)

    # If there are matching semantic rules, format them for the prompt
    if matching_semantic:
        lines = ["known patterns for this source confirmed :"]
        for rule in matching_semantic:
            lines.append(f"- {rule['correction_rule']}")
        return "\n".join(lines)  

    #No semantic rules found for this source, check episodic memory
    episodic_entries = load_episodic_memory(episodic_file)  # Load episodic memory

    matching_episodic = []
    for entry in episodic_entries:
        if entry['source'] == source:
            matching_episodic.append(entry)

    if matching_episodic:
        lines = ["recent learnings for this source :"]
        for entry in matching_episodic:
            lines.append(f"- {entry['correction_rule']} (confidence: {entry['confidence']})")
        return "\n".join(lines)

    return "" # No relevant memory found     


   



