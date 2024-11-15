## This file will contain functions for processing files, including:
## - Reading all PDF filepaths from a directory
## - Reading the contents of a PDF file
## - Updating the filenames of PDFs in a directory

import os
import pdfplumber

def get_pdf_filepaths(directory):
    pdf_titles = {}
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".pdf"):
                pdf_titles[file] = os.path.join(root, file)

    return pdf_titles

def read_pdf(filepath):
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def update_pdf_filenames(directory):
    '''This function will update the filenames of PDFs in a directory based on the first line of text in the PDF. Especially useful as a heuristic when downloading PDFs from ArXiv or elsewhere on the web.'''
    filenames = get_pdf_filepaths(directory)

    for filename in filenames:
        text = ""
        with pdfplumber.open(f"{directory}\\" + filename) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

        paper_title = text.split("\n")[0].replace(":", "").replace(",", "").replace(";", "").replace(".", "").replace("?", "").replace("!", "").replace("'", "").replace('"', "").replace("[", "").replace("]", "").replace("{", "").replace("}", "").replace("/", "").replace("\\", "").replace("|", "").replace("<", "").replace(">", "").replace("=", "").replace("+", "").replace("*", "").replace("&", "").replace("^", "").replace("%", "").replace("#", "").replace("@", "").replace("`", "").replace("~", "") + ".pdf"

        print(f"Current filename: {filename}. Suggested filename: {paper_title}")
        confirmation = input(f"Replace filename?\n")
        if confirmation == "y":
            os.rename(f"{directory}\\" + filename, f"{directory}\\" + paper_title)
            print("Filename updated from " + f"{directory}\\" + filename + " to " + f"{directory}\\" + paper_title)
        else:
            continue