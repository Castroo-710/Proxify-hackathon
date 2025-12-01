import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

try:
    client = genai.Client(api_key=API_KEY)
    for model in client.models.list(config={'page_size': 100}):
        print(model.name)
except Exception as e:
    print(f"Error listing models: {e}")
