import os
import time
import json
from research_details import ResearchContext, DocumentContext, load_json, build_context_prompt
from file_processing import get_pdf_filepaths, read_pdf
from text_processing import LaTeXConverter, ResearchSummariser, CustomLLMCall

def main(user: str = "luke"):
    # Start timer
    start_time = time.time()

    # Get all PDF filepaths from the "documents" directory
    print(f"Getting PDF filepaths. Time elapsed: {time.time() - start_time:.2f} seconds")
    pdf_titles, pdf_count = get_pdf_filepaths("documents")
    time_estimate = pdf_count * 30
    print(f"{pdf_count} PDF files found. Estimated maximum processing time: {time_estimate} seconds")

    # Read the contents of each PDF file
    print(f"Reading PDF files. Time elapsed: {time.time() - start_time:.2f} seconds")
    pdf_texts = load_json("documents\pdf_texts.json")
    pdf_count = 1
    for pdf_title, pdf_filepath in pdf_titles.items():
        print(f"Reading PDF {pdf_count}. Time elapsed: {time.time() - start_time:.2f} seconds")
        if pdf_title not in pdf_texts:
            text = read_pdf(pdf_filepath)
            pdf_texts[pdf_title] = text
        pdf_count += 1

    with open("documents\pdf_texts.json.json", "w", encoding="utf-8") as file:
        file.write(json.dumps(pdf_texts))

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
        all_summaries += f"{pdf_title.split('.')[0]}:\n\n{research_summary}"
        with open(f"summaries/{pdf_title.split('.')[0]}.txt", "w", encoding="utf-8") as file:
            file.write(research_summary)

        summarise_count += 1

    # Convert the summaries to a LaTeX file
    print(f"Converting to LaTeX. Time elapsed: {time.time() - start_time:.2f} seconds")
    latex_converter = LaTeXConverter()
    latex_text = latex_converter.convert_to_latex(all_summaries)

    filename = CustomLLMCall().llm_call("Create a filename for the file containing the following text:\n\n" + latex_text)

    # Save the LaTeX file
    with open("Research-Summaries\main.tex", "w", encoding="utf-8") as file:
        file.write(latex_text.replace("```", "").replace("latex", ""))

    # Wait 20 seconds, then rename "main.tex" to f"{filename}.tex"
    time.sleep(20)
    os.rename("Research-Summaries\main.tex", f"Research-Summaries\{filename}.tex")

    print("Done! Time elapsed: {:.2f} seconds".format(time.time() - start_time))


if __name__ == "__main__":
    user = "luke"
    main(user=user)