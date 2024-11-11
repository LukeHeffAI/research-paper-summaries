from dataclasses import dataclass
import json

# TODO: Create research_data.json with an example entry
with open("data/research_data.json", "r") as file:
    research_data = json.load(file)

# TODO: Create document_data.json with an example entry
with open("data/document_data.json", "r") as file:
    document_data = json.load(file)

@dataclass
class ResearchContext:
    research_field: str
    research_topic: str
    research_interests: str | list[str]

class DocumentContext:
    document_type: str
    document_return_details: str | list[str]

def vowel_check(text):
    return "an " + text if text[0].lower() in "aeiou" else "a " + text

def build_context_prompt(user_context: ResearchContext, document_context: DocumentContext):
    # Research details
    research_field = user_context.research_field
    research_topic = user_context.research_topic
    # TODO: Build an input field to take these individual points and turn them into a list of this structure
    research_interests = "\n\t- " + "\n\t- ".join(user_context.research_interests)
    # TODO: Find a way to make the following more dynamic, changing based on the user's input. Potentially use an OpenAI model to generate the text after the comma based on "research_focus".
    research_statement = f"The general interest in my research is in {research_topic}, with a focus on land based education and building education programs that incorporate indigenous knowledges and pedagogies."
    research_focus_structure = f"The focus points of my research can be summarised as:{research_interests}"

    # Document details
    document_type = document_context.document_type
    document_return_details = "\n\t- ".join(document_context.document_return_details)
    document_prompt_structure = f"I am {vowel_check(research_field.lower())} researcher, needing to summarise a research paper to enable me to write {vowel_check(document_type.lower())}. Please provide a summary of the document below with the following details:{document_return_details}"

    document_intro = "The following text is from a PDF of the document I would like to summarise:"

    # Overall prompt built from the above details
    prompt = f"{document_prompt_structure}\n\n{research_statement} {research_focus_structure}\n\n{document_intro}"

    return prompt