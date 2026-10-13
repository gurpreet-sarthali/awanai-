import os
import sys
import json
from dotenv import load_dotenv

project_root = r"c:\Users\Lenovo\Desktop\my all\code\projects\AI-powered Natural Language Data Analytics Platform"
sys.path.insert(0, project_root)
load_dotenv(os.path.join(project_root, ".env"))

from backend.services.gemini_service import GeminiService

service = GeminiService()

schema = {
    "columns": ["CGPA", "Internship_Experience", "Placement", "Communication_Skills"],
    "types": {"CGPA": "float", "Placement": "int"},
    "allowed_values": {},
}

try:
    print("Testing plan...")
    plan = service.plan("What is the average CGPA?", schema)
    print("Plan succeeded:", plan.model_dump())
    
    print("Testing explain...")
    explanation = service.explain("What is the average CGPA?", "average", 7.85, ["Sample warning"])
    print("Explain succeeded:", explanation.model_dump())
except Exception as e:
    import traceback
    traceback.print_exc()
