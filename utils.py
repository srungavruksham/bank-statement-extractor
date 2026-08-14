import os
import json
import PyPDF2
from pathlib import Path

#Path Safety checking function to ensure the PDF path is within the allowed directory
def validate_path(pdf_path: str, allowed_dir: Path) -> Path:
    path = Path(pdf_path).resolve()
    if not path.is_relative_to(allowed_dir.resolve()):
        raise ValueError(f"Path {pdf_path} is not within the allowed directory {allowed_dir}")
    return path

# Function to extract text from a PDF file
def extract_text_from_pdf(pdf_path: str, allowed_dir: Path) -> str:
    path = validate_path(pdf_path, allowed_dir)
    with open(path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text_parts = [page.extract_text() for page in reader.pages]
    return "\n".join(text_parts)

def parse_json_response(response_str):
    result_str = str(response_str)
    if '```json' in result_str:
        result_str = result_str.split('```json')[1].split('```')[0].strip()
    elif '```' in result_str:
        result_str = result_str.split('```')[1].split('```')[0].strip()

    try:
        return json.loads(result_str)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Failed to parse response: {result_str}", e.doc, e.pos)