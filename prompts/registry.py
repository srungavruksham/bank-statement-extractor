import os
from pathlib import Path
import json
import yaml

def get_prompt(agent_name:str , **kwargs) -> str:
    """
    agent_name: e.g. "identity", "account", "transactions", "merge"
    kwargs: the values to fill into the template, e.g. document_text="..."
    """
    prompt_path = Path(os.path.dirname(__file__)) / f"{agent_name}.yaml"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file for agent '{agent_name}' not found at {prompt_path}")
    
    data = yaml.safe_load(prompt_path.read_text())
    versions = data["versions"]
    latest = max(versions, key = lambda v: v.get("version", 0))
    template = latest["template"]
    return template.format(**kwargs)


def get_prompt_version(agent_name: str):
    """
    Return the version identifier of the latest prompt version for an agent,
    so the pipeline can record which prompt version each run actually used.
    """
    prompt_path = Path(os.path.dirname(__file__)) / f"{agent_name}.yaml"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file for agent '{agent_name}' not found at {prompt_path}")

    data = yaml.safe_load(prompt_path.read_text())
    versions = data["versions"]
    latest = max(versions, key=lambda v: v.get("version", 0))
    return latest.get("version")
    

    

