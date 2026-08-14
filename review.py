import json
import uuid
from pathlib import Path
from datetime import datetime


# when a human approves a run, we save the final result on its own, away from the
# raw pipeline output. one file per approval, named after the run_id so we can
# always trace it back to the run that produced it.
def save_approved_result(result, approved_dir="data/approved"):
    Path(approved_dir).mkdir(parents=True, exist_ok=True)  # make the folder if it isn't there yet

    run_id = result.get("run_id") or str(uuid.uuid4())  # fall back to a fresh id just in case

    # only keep the bits a human actually confirmed, plus a bit of context
    record = {
        "run_id": run_id,
        "source": result.get("source"),
        "approved_at": datetime.now().isoformat(),
        "merged_data": result.get("merged_data"),
        "validation_result": result.get("validation_result"),
        "reflection_result": result.get("reflection_result"),
        "prompt_versions": result.get("prompt_versions"),
    }

    out_path = Path(approved_dir) / f"{run_id}.json"
    with open(out_path, "w") as f:
        json.dump(record, f, indent=4)

    return str(out_path)  # hand the path back so the caller can show it
