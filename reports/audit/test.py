import os
from openai import OpenAI

# 1. Product Specialist Config: Setting up the DeepSeek endpoint
# Best practice: Fetch the key from environment variables
client = OpenAI(
    api_key="sk-27a16c7a57dc4cb198bc95d2801e80e7", 
    base_url="https://api.deepseek.com"
)

def analyze_text_deepseek(input_text):
    """
    Leverages DeepSeek's reasoning to extract sentiment and key insights.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat", # Use "deepseek-reasoner" for R1/Thinking mode
            messages=[
                {"role": "system", "content": "You are a professional text analyst. Provide concise sentiment, tone, and key takeaways."},
                {"role": "user", "content": f"Analyze this text: {input_text}"},
            ],
            stream=False
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"QA Analysis Error: {str(e)}"

# Example Usage
text_to_process = "DeepSeek's new open-weights models are disrupting the industry by providing GPT-4 level performance at a fraction of the cost."
print(analyze_text_deepseek(text_to_process))