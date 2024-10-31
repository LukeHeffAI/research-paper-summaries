import openai
import os
from dotenv import load_dotenv
from research_details import build_context_prompt
from file_processing import get_pdf_filepaths, read_pdf

# Get the API key from the .env file using the dotenv api_key = package
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

max_tokens = 400

# Base class for handling different types of OpenAI text operations
class OpenAITextProcessor: #TODO: Test this class
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
    
# Class for handling text summarization using OpenAI
class ResearchSummariser(OpenAITextProcessor):
    def __init__(self, model="gpt-4o-mini", max_tokens=max_tokens):
        super().__init__(model, max_tokens)
    
    def summarise_text(self, text):
        system_content = "You are a helpful assistant."
        user_content = text
        return self._create_response(system_content, user_content)
    

# summariser = ResearchSummariser()
# print(summariser.summarise_text(f"Cinco de Mayo in Mexico, Spanish for 'Fifth of May') is an annual celebration held on May 5 to celebrate Mexico's victory over the Second French Empire at the Battle of Puebla in 1862,[1][2] led by General Ignacio Zaragoza. Zaragoza died months after the battle from an illness, however, and a larger French force ultimately defeated the Mexican army at the Second Battle of Puebla and then occupied Mexico City. Following the end of the American Civil War in 1865, the United States began lending money and guns to the Mexican Liberals, pushing France and Mexican Conservatives to the edge of defeat. At the opening of the French chambers in January 1866, Napoleon III announced that he would withdraw French troops from Mexico. In reply to a French request for American neutrality, the American secretary of state William H. Seward replied that French withdrawal from Mexico should be unconditional."))