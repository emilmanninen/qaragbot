#just testing for available mmodles
from dotenv import load_dotenv
from google import genai

load_dotenv()  # loads GEMINI_API_KEY from .env, same as your other scripts rely on session.py to do

client = genai.Client()
for model in client.models.list():
    print(model.name, "-", model.supported_actions)