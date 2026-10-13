import os
import sys
from dotenv import load_dotenv

project_root = r"c:\Users\Lenovo\Desktop\my all\code\projects\AI-powered Natural Language Data Analytics Platform"
load_dotenv(os.path.join(project_root, ".env"))

api_key = os.getenv("GEMINI_API_KEY")

from google import genai

client = genai.Client(api_key=api_key)

models_to_test = ["gemini-3.8-flash", "models/gemini-3.8-flash"]
for m in models_to_test:
    try:
        resp = client.models.generate_content(
            model=m,
            contents="Hello, reply with only the word OK.",
        )
        print(f"SUCCESS with {m}:", resp.text.strip())
        break
    except Exception as e:
        print(f"FAILED with {m}:", e)
