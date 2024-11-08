from dataclasses import dataclass
import json

with open("research_data.json", "r") as file:
    research_data = json.load(file)

# TODO:
with open("document_data.json", "r") as file:
    document_data = json.load(file)

@dataclass
class ResearchContext:
    research_field: str
    research_topic: str
    research_context: str
    research_focus: str
    document_intro: str

class DocumentContext:
    document_type: str
    document_return_details: str

def vowel_check(text):
    return "an " + text if text[0].lower() in "aeiou" else "a " + text

def build_context_prompt(user_context: ResearchContext):
    # Research details
    research_field = "Anthropology"
    research_topic = "Indigenous studies in Australia"
    # TODO: Build an input field to take these individual points and turn them into a list of this structure
    research_focus = """
    - Learning on-country principles 
    - Meaning of 'Country' in indigenous contexts
    - Settler colonial theory 
    - Land education/pedagogy and curriculum development"""
    # TODO: Find a way to make the following more dynamic, changing based on the user's input. Potentially use an OpenAI model to generate the text after the comma based on "research_focus".
    research_interests = f"The general interest in my research is in {research_topic}, with a focus on land based education and building education programs that incorporate indigenous knowledges and pedagogies."
    research_focus_structure = f"The focus points of my research can be summarised as:{research_focus}"

    # Document details
    document_type = "Literature review"
    document_return_details = """
    - A summary of the overall document, of roughly 300 words
    - What does "learning on-country" mean?
    - Key findings
    - Contributions to the field
    - Gaps remaining"""
    document_prompt_structure = f"I am {vowel_check(research_field.lower())} researcher, needing to summarise a research paper to enable me to write {vowel_check(document_type.lower())}. Please provide a summary of the document below with the following details:{document_return_details}"

    document_intro = "The following text is from a PDF of the document I would like to summarise:"

    # Overall prompt built from the above details
    prompt = f"{document_prompt_structure}\n\n{research_interests} {research_focus_structure}\n\n{document_intro}"

    return prompt