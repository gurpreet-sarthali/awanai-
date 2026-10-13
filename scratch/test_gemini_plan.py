import os
import sys
from dotenv import load_dotenv

project_root = r"c:\Users\Lenovo\Desktop\my all\code\projects\AI-powered Natural Language Data Analytics Platform"
sys.path.insert(0, project_root)
load_dotenv(os.path.join(project_root, ".env"))

os.environ["GEMINI_MODEL"] = "gemini-3.8-flash"

from backend.services.gemini_service import GeminiService

service = GeminiService(model="gemini-3.8-flash")
schema = {
    "columns": ["CGPA", "Internship_Experience", "Placement", "Communication_Skills"],
    "types": {"CGPA": "float", "Placement": "int"},
    "allowed_values": {},
}

try:
    plan = service.plan("What is the average CGPA?", schema)
    print("SUCCESSFUL PLAN:", plan.model_dump())
except Exception as e:
    import traceback
    traceback.print_exc()
