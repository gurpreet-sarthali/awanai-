import os
import sys
from dotenv import load_dotenv

project_root = r"c:\Users\Lenovo\Desktop\my all\code\projects\AI-powered Natural Language Data Analytics Platform"
load_dotenv(os.path.join(project_root, ".env"))

api_key = os.getenv("GEMINI_API_KEY")

from google import genai

client = genai.Client(api_key=api_key)

test_candidates = [
    "gemini-2.5-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
]

for m in test_candidates:
    try:
        resp = client.models.generate_content(
            model=m,
            contents="Say hello in 2 words",
        )
        print(f"PASS {m}: {resp.text.strip()}")
    except Exception as e:
        status = getattr(e, 'code', None) or getattr(e, 'status_code', None)
        print(f"FAIL {m} [{status}]: {e}")
