import os
import time
from research_details import build_context_prompt
from file_processing import get_pdf_filepaths, read_pdf
from text_processing import LaTeXConverter, ResearchSummariser

def main():
    # Start timer
    start_time = time.time()

    # Get all PDF filepaths from the "documents" directory
    print(f"Getting PDF filepaths. Time elapsed: {time.time() - start_time:.2f} seconds")
    pdf_titles = get_pdf_filepaths("documents")

    # Read the contents of each PDF file
    print(f"Reading PDF files. Time elapsed: {time.time() - start_time:.2f} seconds")
    pdf_texts = {}
    pdf_count = 1
    for pdf_title, pdf_filepath in pdf_titles.items():
        print(f"Reading PDF {pdf_count}. Time elapsed: {time.time() - start_time:.2f} seconds")
        text = read_pdf(pdf_filepath)
        pdf_texts[pdf_title] = text
        pdf_count += 1

    # Build the research context prompt
    research_prompt = build_context_prompt()

    # Summarise each PDF file using OpenAI, prepending the research context prompt to each text
    print(f"Summarising PDF files. Time elapsed: {time.time() - start_time:.2f} seconds")
    research_summariser = ResearchSummariser()
    summarise_count = 1
    all_summaries = "Title: Research Summaries\n\n"
    for pdf_title, pdf_text in pdf_texts.items():
        full_text = f"{research_prompt}\n\n{pdf_text}"

        # Summarise the full text
        print(f"Summarising PDF {summarise_count}. Time elapsed: {time.time() - start_time:.2f} seconds")
        research_summary = research_summariser.summarise_text(full_text)
        all_summaries += f"{pdf_title.split('.')[0]}:\n\n{research_summary}\n\n"
        with open(f"summaries/{pdf_title.split('.')[0]}.txt", "w") as file:
            file.write(research_summary.replace("\\u2",""))
        summarise_count += 1

    # Convert the summaries to a LaTeX file
    print(f"Converting to LaTeX. Time elapsed: {time.time() - start_time:.2f} seconds")
    latex_converter = LaTeXConverter()
    latex_text = latex_converter.convert_to_latex(all_summaries)

    # Save the LaTeX file
    with open("Research-Summaries\main.tex", "w") as file:
        file.write(latex_text.replace("```", "").replace("latex", ""))

    print("Done! Time elapsed: {:.2f} seconds".format(time.time() - start_time))


if __name__ == "__main__":
    main()