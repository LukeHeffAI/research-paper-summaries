from research_details import build_context_prompt
from file_processing import get_pdf_filepaths, read_pdf
from text_processing import ResearchSummariser

def main():
    # Get all PDF filepaths from the "documents" directory
    pdf_titles = get_pdf_filepaths("documents")

    # Read the contents of each PDF file
    pdf_texts = {}
    for pdf_title, pdf_filepath in pdf_titles.items():
        text = read_pdf(pdf_filepath)
        pdf_texts[pdf_title] = text

    research_prompt = build_context_prompt()

    # Summarise each PDF file using OpenAI, prepending the research context prompt to each text
    summariser = ResearchSummariser()
    for pdf_title, pdf_text in pdf_texts.items():
        full_text = f"{research_prompt}\n\n{pdf_text}"

        print(full_text)

        summary = summariser.summarise_text(full_text)
        with open(f"summaries/{pdf_title}.txt", "w") as file:
            file.write(summary)


if __name__ == "__main__":
    main()