import os
from openai import OpenAI
from dotenv import load_dotenv

# 1. Load your API key from .env
load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    print("❌ ERROR: OPENROUTER_API_KEY not found in .env file.")
    exit(1)

# 2. Initialize the client with OpenRouter's base URL
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
    default_headers={
        "HTTP-Referer": "http://localhost:3000", # Required for OpenRouter rankings
        "X-Title": "Connectivity Test Script",     # Optional
    }
)

def test_connection(model_name="openai/gpt-4o-mini"):
    print(f"--- Testing Connection to OpenRouter ({model_name}) ---")
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a connectivity tester."},
                {"role": "user", "content": "Respond with the word 'READY' and nothing else."}
            ]
        )
        
        response_text = completion.choices[0].message.content.strip()
        print(f"✅ SUCCESS: Model responded: {response_text}")
        print(f"Provider used: {completion.model}")
        
    except Exception as e:
        print(f"❌ CONNECTION FAILED")
        print(f"Error details: {str(e)}")

if __name__ == "__main__":
    # Test with a lightweight model first
    test_connection()