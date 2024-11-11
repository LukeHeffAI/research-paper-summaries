import os
import time
import json
import subprocess
from research_details import ResearchContext, DocumentContext, load_json, build_context_prompt
from file_processing import get_pdf_filepaths, read_pdf
from text_processing import LaTeXConverter, ResearchSummariser, CustomLLMCall

def main(user: str, overwrite: bool = False):
    # Start timer
    start_time = time.time()

    # Check if user directory exists and create it and necessary files if not
    # TODO: Move this into a class method in a new class called "NewUserHandler"
    if not os.path.exists(f"users\{user}"):
        os.makedirs(f"users\{user}\documents")
        os.makedirs(f"users\{user}\summaries")
        with open(f"users\{user}\documents\pdf_texts.json", "w", encoding="utf-8") as file:
            file.write("{}")
        raise FileNotFoundError(f"Directory 'users\{user}\documents' does not exist. Creating this directory for you now. Add your PDF files to this directory and run the script again.")

    # Get all PDF filepaths from the "documents" directory
    print(f"Getting PDF filepaths. Time elapsed: {time.time() - start_time:.2f} seconds")
    pdf_titles = get_pdf_filepaths(f"users\{user}\documents")
    print(f"{len(pdf_titles)} PDF filepaths found")

    # Read the contents of each PDF file
    print(f"Reading PDF files. Time elapsed: {time.time() - start_time:.2f} seconds")
    pdf_texts = load_json(f"users\{user}\documents\pdf_texts.json")
    pdf_count = 1
    for pdf_title, pdf_filepath in pdf_titles.items():
        print(f"Reading PDF {pdf_count}. Time elapsed: {time.time() - start_time:.2f} seconds")
        if pdf_title not in pdf_texts:
            text = read_pdf(pdf_filepath)
            pdf_texts[pdf_title] = text
        pdf_count += 1

    print(f"All PDFs loaded/read. Saving PDF texts. Time elapsed: {time.time() - start_time:.2f} seconds")
    with open(f"users\{user}\documents\pdf_texts.json", "w", encoding="utf-8") as file:
        file.write(json.dumps(pdf_texts))

    # Build the research context prompt
    research_data = load_json("data/research_data.json")["users"][user]
    document_data = load_json("data/document_data.json")
    research_context = ResearchContext(**research_data)
    document_context = DocumentContext(**document_data)
    research_prompt = build_context_prompt(research_context, document_context)

    # Summarise each PDF file using OpenAI, prepending the research context prompt to each text
    print(f"Summarising PDF files. Time elapsed: {time.time() - start_time:.2f} seconds")
    research_summariser = ResearchSummariser()
    summarise_count = 1
    all_summaries = "Title: Research Summaries\n\n"
    for pdf_title, pdf_text in pdf_texts.items():

        # Summarise the full text
        if pdf_title.split('.')[0] + ".txt" not in os.listdir(f"users\{user}\summaries") or overwrite:
            print(f"Summarising PDF {summarise_count}. Time elapsed: {time.time() - start_time:.2f} seconds")
            full_text = f"{research_prompt}\n\n{pdf_text}"
            research_summary = research_summariser.summarise_text(full_text)
            with open(f"users\{user}\summaries/{pdf_title.split('.')[0]}.txt", "w", encoding="utf-8") as file:
                file.write(research_summary)
            all_summaries += f"{pdf_title.split('.')[0]}:\n\n{research_summary}\n\n"
        else:
            print(f"Reading existing summary for PDF {summarise_count}. Time elapsed: {time.time() - start_time:.2f} seconds")
            with open(f"users\{user}\summaries/{pdf_title.split('.')[0]}.txt", "r", encoding="utf-8") as file:
                research_summary = file.read()
            all_summaries += f"{pdf_title.split('.')[0]}:\n\n{research_summary}\n\n"

        summarise_count += 1

    # Convert the summaries to a LaTeX file
    print(f"Converting to LaTeX. Time elapsed: {time.time() - start_time:.2f} seconds")
    latex_text = LaTeXConverter().convert_to_latex(all_summaries)

    # Create a filename for the LaTeX file
    print(f"Creating filename. Time elapsed: {time.time() - start_time:.2f} seconds")
    filename = CustomLLMCall().llm_call("Create a filename for the file containing the following text. Do not return anything but the filename as this will be inserted straight into code used to modify the filename:\n\n" + all_summaries[:5000])

    # Save the LaTeX file
    with open("Research-Summaries\main.tex", "w", encoding="utf-8") as file:
        file.write(latex_text.replace("```", "").replace("latex", ""))

    # Wait 20 seconds, then rename "main.tex" to f"{filename}.tex"
    print("Building summary report. Time elapsed: {:.2f} seconds. This should take roughly 30 seconds.".format(time.time() - start_time))
    time.sleep(20)
    os.rename("Research-Summaries\main.pdf", f"users\{user}\summaries{filename}.pdf")

    print("Done! Time elapsed: {:.2f} seconds".format(time.time() - start_time))


if __name__ == "__main__":
    user = "luke"
    main(user=user)