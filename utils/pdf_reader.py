from PyPDF2 import PdfReader

def extract_text(pdf_path):
    text = ""

    reader = PdfReader(pdf_path)

    for page in reader.pages:
        text += page.extract_text()

    return text