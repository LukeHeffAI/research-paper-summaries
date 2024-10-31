## This file will contain functions for processing files, including:
## - Reading all PDF filepaths from a directory
## - Reading the contents of a PDF file
## - Creating PDF files from text strings

import os
from PyPDF2 import PdfFileReader, PdfFileWriter

def get_pdf_filepaths(directory):
    pdf_filepaths = []
    for file in os.listdir(directory):
        if file.endswith(".pdf"):
            pdf_filepaths.append(os.path.join(directory, file))
    return pdf_filepaths

def read_pdf(filepath):
    with open(filepath, "rb") as file:
        pdf = PdfFileReader(file)
        text = ""
        for page_num in range(pdf.getNumPages()):
            page = pdf.getPage(page_num)
            text += page.extract_text()
        return text
    
def create_pdf_from_text(text, output_filepath): # TODO: trial this function
    pdf = PdfFileWriter()
    pdf.addPage()
    pdf.getPage(0).addText(text)
    with open(output_filepath, "wb") as file:
        pdf.write(file)