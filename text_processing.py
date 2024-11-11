import openai
import os
from dotenv import load_dotenv
from research_details import build_context_prompt
from file_processing import get_pdf_filepaths, read_pdf

# Get the API key from the .env file using the dotenv api_key = package
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

max_tokens = 4096
model = "gpt-4o-mini" # Use gpt-4o-mini for testing, gpt-4o for production

# Base class for handling different types of OpenAI text operations
class OpenAITextProcessor:
    def __init__(self, model=model, max_tokens=max_tokens):
        self.model = model
        self.max_tokens = max_tokens
    
    def _create_response(self, system_content, user_content):
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0,
            max_tokens=self.max_tokens,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        return response['choices'][0]['message']['content']
    
class CustomLLMCall(OpenAITextProcessor):
    def __init__(self, model="gpt-4o-mini", max_tokens=16384):
        super().__init__(model, max_tokens)
    
    def llm_call(self, text):
        system_content = "You are a helpful assistant."
        user_content = text
        return self._create_response(system_content, user_content)
    
class GeneralSummariser(OpenAITextProcessor):
    def __init__(self, model=model, max_tokens=16384):
        super().__init__(model, max_tokens)
    
    def summarise_text(self, text):
        system_content = "You are a helpful assistant."
        user_content = "Summarise the overall information in the following text in 400 words or less:\n\n" + text
        return self._create_response(system_content, user_content)
    
# Class for handling text summarization using OpenAI
class ResearchSummariser(OpenAITextProcessor):
    def __init__(self, model=model, max_tokens=max_tokens):
        super().__init__(model, max_tokens)
    
    def summarise_text(self, text):
        system_content = "You are a helpful assistant."
        user_content = text
        return self._create_response(system_content, user_content)
    
# Class for converting text into a LaTeX style document section
class LaTeXConverter(OpenAITextProcessor):
    def __init__(self, model="gpt-4o-mini", max_tokens=16384):
        super().__init__(model, max_tokens)
    
    def convert_to_latex(self, text):
        system_content = "You are a helpful assistant."
        user_content = "Convert the following series of research paper summaries into a LaTeX document. Solely return the LaTeX content; no filler, language markers, or discussion. Add a contents page at the start. Each paper should have a new page created for it. Use the name of each paper as sections. Bold any text that was surrounded by double asterisks ('**') and remove the asterisks. Make subsections and subsubsections as needed.\n\nThe text is as follows:\n\n" + text
        return self._create_response(system_content, user_content)




# summariser = ResearchSummariser()
# latex_converter = LaTeXConverter()
# summarised_text = summariser.summarise_text(f"Cinco de Mayo in Mexico, Spanish for 'Fifth of May') is an annual celebration held on May 5 to celebrate Mexico's victory over the Second French Empire at the Battle of Puebla in 1862,[1][2] led by General Ignacio Zaragoza. Zaragoza died months after the battle from an illness, however, and a larger French force ultimately defeated the Mexican army at the Second Battle of Puebla and then occupied Mexico City. Following the end of the American Civil War in 1865, the United States began lending money and guns to the Mexican Liberals, pushing France and Mexican Conservatives to the edge of defeat. At the opening of the French chambers in January 1866, Napoleon III announced that he would withdraw French troops from Mexico. In reply to a French request for American neutrality, the American secretary of state William H. Seward replied that French withdrawal from Mexico should be unconditional.")
# latex_text = latex_converter.convert_to_latex(summarised_text)
# print(latex_text)