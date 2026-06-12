from google import genai

client = genai.Client(api_key="Gemini_api_key")

print("Available Models and Versions:")
for model in client.models.list():
    print(f"-> Name: {model.name}")
    print(f"   Version: {model.version}")
    print(f"   Actions: {model.supported_actions}\n")
