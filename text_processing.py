import openai
import os
from dotenv import load_dotenv

# Get the API key from the .env file using the dotenv api_key = package
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

max_tokens = 4096

# Base class for handling different types of OpenAI text operations
class OpenAITextProcessor:
    def __init__(self, model="gpt-4o-mini", max_tokens=max_tokens):
        self.model = model
        self.max_tokens = max_tokens
    
    def _create_response(self, system_content, user_content):
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            max_tokens=self.max_tokens,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        return response['choices'][0]['message']['content']