import json
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path("../../.env"))

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.agent import parse_profile_from_text
from app.models import ProjectProfile

DATASETS_DIR = Path(__file__).parent.parent / "datasets"

async def run_evaluation():
    print("Starting On-Chain LLM Agent Evaluation...")
    total_cases = 0
    passed_cases = 0

    if not DATASETS_DIR.exists():
        print(f"Error: Datasets directory not found at {DATASETS_DIR}")
        return

    for file_path in DATASETS_DIR.glob("*.json"):
        with open(file_path, "r") as f:
            data = json.load(f)

        document_text = data.get("document_text")
        expected_profile = data.get("expected_profile")
        
        if not document_text or not expected_profile:
            print(f"Skipping {file_path.name}: Invalid structure.")
            continue
            
        total_cases += 1
        print(f"\nEvaluating: {data.get('case_name', file_path.name)}")
        
        try:
            extracted_profile = await parse_profile_from_text(document_text)
            
            # Simple exact match comparison for key fields
            passed = True
            for key, expected_value in expected_profile.items():
                actual_value = getattr(extracted_profile, key, None)
                if hasattr(actual_value, "value"): # Handle Enums
                    actual_value = actual_value.value
                    
                if actual_value != expected_value:
                    print(f"  ❌ Mismatch on '{key}': Expected '{expected_value}', Got '{actual_value}'")
                    passed = False
                    
            if passed:
                print("  ✅ Passed")
                passed_cases += 1
                
        except Exception as e:
            print(f"  ❌ Failed with error: {e}")

    print(f"\n=== Evaluation Summary ===")
    print(f"Total Cases: {total_cases}")
    print(f"Passed: {passed_cases}")
    print(f"Accuracy: {(passed_cases/max(1, total_cases))*100:.1f}%")

if __name__ == "__main__":
    asyncio.run(run_evaluation())