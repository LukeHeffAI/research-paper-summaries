from research_details import build_context_prompt
from file_processing import get_pdf_filepaths, read_pdf
from text_processing import LaTeXConverter, GeneralSummariser, ResearchSummariser

def main():
    # Get all PDF filepaths from the "documents" directory
    print("Getting PDF filepaths...")
    pdf_titles = get_pdf_filepaths("documents")

    # Read the contents of each PDF file
    print("Reading PDF files...")
    pdf_texts = {}
    for pdf_title, pdf_filepath in pdf_titles.items():
        text = read_pdf(pdf_filepath)
        pdf_texts[pdf_title] = text

    # Build the research context prompt
    research_prompt = build_context_prompt()

    # Summarise each PDF file using OpenAI, prepending the research context prompt to each text
    research_summariser = ResearchSummariser()
    count = 1
    for pdf_title, pdf_text in pdf_texts.items():
        full_text = f"{research_prompt}\n\n{pdf_text}"

        print(full_text)

        # Summarise the full text
        research_summary = research_summariser.summarise_text(full_text)
        with open(f"summaries/{pdf_title}.txt", "w") as file:
            file.write(research_summary)

        # Save the summary to a text file
        with open(f"summaries/{pdf_title.split('.')[0]}.txt", "w") as file:
            file.write(research_summary)

    # Concatenate the text from each of the text files, separated by two newlines
    all_summaries = "Research Summaries\n\n"
    for pdf_title in pdf_titles:
        with open(f"summaries/{pdf_title.split('.')[0]}.txt", "r") as file:
            all_summaries += file.read() + "\n\n"

    # Save the concatenated text to a single text file
    with open("summaries/all_summaries.txt", "w") as file:
        file.write(all_summaries)

    # Convert the summaries to a LaTeX file
    latex_converter = LaTeXConverter()
    latex_text = latex_converter.convert_to_latex(all_summaries)

    # Save the LaTeX file
    with open("Research-Summaries\main.tex", "w") as file:
        file.write(latex_text)

    print("Done!")         




if __name__ == "__main__":
    main()