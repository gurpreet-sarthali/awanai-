import os
import sys
from dotenv import load_dotenv

project_root = r"c:\Users\Lenovo\Desktop\my all\code\projects\AI-powered Natural Language Data Analytics Platform"
load_dotenv(os.path.join(project_root, ".env"))

api_key = os.getenv("GEMINI_API_KEY")

from google import genai

client = genai.Client(api_key=api_key)

try:
    models = list(client.models.list())
    print("Found", len(models), "models:")
    for m in models:
        methods = getattr(m, "supported_generation_methods", []) or getattr(m, "supported_actions", [])
        print(f" - {m.name}: {methods}")
except Exception as e:
    print("List failed:", e)
