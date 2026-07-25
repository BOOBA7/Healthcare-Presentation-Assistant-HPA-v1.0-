from app.core.config import get_settings
from app.ai.llm.llm import get_llm

settings = get_settings()

print("Provider:", settings.llm_provider)
print("Model:", settings.gemini_model)

llm = get_llm()

response = llm.invoke("Say only: Hello Healthcare AI")

print(response.text)
