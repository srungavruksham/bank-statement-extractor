from dotenv import load_dotenv
import os
import json
from pathlib import Path
from crewai_extraction import extract_and_merge, create_reflection_agent, create_reflection_task, run_agent
from utils import extract_text_from_pdf
from validation import validate_merged_data
from memory.store import format_memory_for_prompt, add_episodic_entry, check_for_promotion
from telemetry.tracker import summarize_run
from prompts import registry
import uuid

load_dotenv()  # Load environment variables from .env file

llm = os.getenv("LLM_MODEL","gemini/gemini-3.5-flash")  


def run_pipeline(pdf_path, allowed_dir, source, run_id = None,telemetry_file ="telemetry/data/calls.json",
                 episodic_file="memory/data/episodic.json", semantic_file="memory/data/semantic.json"):

    if run_id is None:
        run_id = str(uuid.uuid4())  # Generate a new UUID if not provided
    #
    #
    source = (source or "").strip().lower()
    if not source:
        source = "unknown"

    #Step 1: Extract text from PDF
    try:
        document_text = extract_text_from_pdf(pdf_path, allowed_dir)
    except (ValueError, FileNotFoundError) as e:
        #
        yield {
            "stage": "error",
            "run_id": run_id,
            "source": source,
            "merged_data": None,
            "validation_result": None,
            "reflection_result": None,
            "telemetry": None,
            "prompt_versions": None,
            "error": str(e),
        }
        return

    yield {
        "stage": "text_extracted",
        "run_id": run_id,
        "source": source,
        "char_count": len(document_text),
    }

    # Step 2: Read any learned corrections for this source and extract + merge data using the LLM
    memory_context = format_memory_for_prompt(source, episodic_file, semantic_file)
    merged_data = extract_and_merge(llm, document_text,run_id,telemetry_file,memory_context)

    yield {
        "stage": "extracted_merged",
        "run_id": run_id,
        "merged_data": merged_data,
        "telemetry": summarize_run(telemetry_file, run_id),
    }

    # Step 3: Validate the merged data
    validation_result = validate_merged_data(merged_data)

    yield {
        "stage": "validated",
        "run_id": run_id,
        "validation_result": validation_result,
    }

    reflection_result = None

    if not validation_result["is_valid"]:
        # Step 4: Create a reflection agent and task to handle validation errors
        reflection_agent = create_reflection_agent(llm)
        reflection_task = create_reflection_task(reflection_agent, document_text, validation_result["errors"])

        # Step 5: Run the reflection agent to get a response
        reflection_result = run_agent(reflection_agent, reflection_task,telemetry_file, run_id, agent_name="reflection_agent", model=llm)

        # Step 6: Persist the learning to episodic memory, then promote it if the same mistake is seen multiple times
        saved_to_memory = False
        if reflection_result and reflection_result.get("correction_rule"):
            add_episodic_entry(
                episodic_file,
                source,
                reflection_result.get("mistake_description"),
                reflection_result.get("correction_rule"),
                reflection_result.get("confidence"),
            )
            check_for_promotion(episodic_file, semantic_file, threshold=2)
            saved_to_memory = True

        yield {
            "stage": "reflected",
            "run_id": run_id,
            "reflection_result": reflection_result,
            "saved_to_memory": saved_to_memory,
        }

    # Record which prompt version each agent used this run.
    prompt_versions = {
        "identity": registry.get_prompt_version("identity"),
        "account": registry.get_prompt_version("account"),
        "transactions": registry.get_prompt_version("transactions"),
        "merge": registry.get_prompt_version("merge"),
    }
    if reflection_result is not None:
        prompt_versions["reflection"] = registry.get_prompt_version("reflection")

    
    yield {
        "stage": "complete",
        "run_id": run_id,
        "source": source,
        "merged_data": merged_data,
        "validation_result": validation_result,
        "reflection_result": reflection_result,
        "telemetry": summarize_run(telemetry_file, run_id),
        "prompt_versions": prompt_versions,
        "error": None,
    }


