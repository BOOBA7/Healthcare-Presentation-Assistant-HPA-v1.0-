from google import genai
from app.core.config import get_settings

settings = get_settings()
if not settings.gemini_api_key:
    raise RuntimeError("GEMINI_API_KEY must be configured in .env")

client = genai.Client(api_key=settings.gemini_api_key)

for model in client.models.list():
    print(model.name)
