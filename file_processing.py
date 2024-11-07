## This file will contain functions for processing files, including:
## - Reading all PDF filepaths from a directory
## - Reading the contents of a PDF file

import os
import pdfplumber

def get_pdf_filepaths(directory):
    pdf_titles = {}
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".pdf"):
                pdf_titles[file] = os.path.join(root, file)

    pdf_count = len(pdf_titles)
    print(f"{pdf_count} PDF filepaths found")

    return pdf_titles, pdf_count

def read_pdf(filepath):
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text