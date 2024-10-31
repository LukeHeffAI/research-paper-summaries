## This file will contain functions for processing files, including:
## - Reading all PDF filepaths from a directory
## - Reading the contents of a PDF file
## - Creating PDF files from text strings

import os
from PyPDF2 import PdfFileWriter
import pdfplumber

def get_pdf_filepaths(directory):
    pdf_titles = {}
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".pdf"):
                pdf_titles[file] = os.path.join(root, file)

    print(f"{len(pdf_titles)} PDF filepaths found")

    return pdf_titles

def read_pdf(filepath):
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""  # handle pages with no text gracefully
    return text
    
# def create_pdf_from_text(text, output_filepath): # TODO: trial this function
#     pdf = PdfFileWriter()
#     pdf.addPage()
#     pdf.getPage(0).addText(text)
#     with open(output_filepath, "wb") as file:
#         pdf.write(file)

# pdf_titles = get_pdf_filepaths("documents")
# print(pdf_titles.values())

# for pdf_title, pdf_filepath in pdf_titles.items():
#     text = read_pdf(pdf_filepath)
#     print("\nAnalysing text from", pdf_title)