from dataclasses import dataclass
import json

@dataclass
class ResearchContext:
    research_field: str
    research_topic: str
    research_interests: str | list[str]
    research_focus: str

@dataclass
class DocumentContext:
    document_type: str
    document_return_details: str | list[str]

def load_json(file_path):
    with open(file_path, "r") as file:
        return json.load(file)

def vowel_check(text):
    return "an " + text if text[0].lower() in "aeiou" else "a " + text

def build_context_prompt(user_context: ResearchContext, document_context: DocumentContext):
    # Research details
    # TODO: Find a way to make the following more dynamic, changing based on the user's input. Potentially use an OpenAI model to generate the text after the comma based on "research_focus".
    research_statement = f"The general interest of my research is in {user_context.research_topic}, with a focus on {user_context.research_focus}."
    research_interests = "\n\t- " + "\n\t- ".join(user_context.research_interests) if isinstance(user_context.research_interests, list) else f"\n\t- {user_context.research_interests}"
    research_focus_structure = f"The focus topics of my research can be summarised as:{research_interests}"

    # Document details
    document_return_details = "\n\t- " + "\n\t- ".join(document_context.document_return_details) if isinstance(document_context.document_return_details, list) else f"\n\t- {document_context.document_return_details}"
    document_prompt_structure = f"I am {vowel_check(user_context.research_field.lower())} researcher, needing to summarise a research paper to enable me to write {vowel_check(document_context.document_type.lower())}."

    document_intro = f"Please provide a summary of the document below with the following details:{document_return_details}.\n\nThe following text is from a PDF of the document I would like to summarise:"

    # Overall prompt built from the above details
    prompt = f"{document_prompt_structure} {research_statement} {research_focus_structure}\n\n{document_intro}"

    return prompt

user = "luke"

research_data = load_json("data/research_data.json")["users"][user]
document_data = load_json("data/document_data.json")

research_context = ResearchContext(**research_data)
document_context = DocumentContext(**document_data)

context_prompt = build_context_prompt(research_context, document_context)

print(context_prompt)