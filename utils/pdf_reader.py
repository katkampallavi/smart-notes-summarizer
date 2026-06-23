import os


def extract_text_from_pdf(filepath):
    """
    Extract text content from a PDF file.
    Uses PyMuPDF (fitz) as primary, falls back to pdfplumber.
    Returns extracted text as a string.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"PDF file not found: {filepath}")

    text = ""

    # Primary: PyMuPDF (fitz)
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(filepath)
        pages_text = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text("text")
            if page_text.strip():
                pages_text.append(page_text.strip())
        doc.close()
        text = "\n\n".join(pages_text)
        if text.strip():
            return _clean_extracted_text(text)
    except ImportError:
        pass
    except Exception as e:
        print(f"[PyMuPDF] Error reading PDF: {e}")

    # Fallback: pdfplumber
    try:
        import pdfplumber
        pages_text = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    pages_text.append(page_text.strip())
        text = "\n\n".join(pages_text)
        if text.strip():
            return _clean_extracted_text(text)
    except ImportError:
        pass
    except Exception as e:
        print(f"[pdfplumber] Error reading PDF: {e}")

    # Last resort: pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        pages_text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                pages_text.append(page_text.strip())
        text = "\n\n".join(pages_text)
        if text.strip():
            return _clean_extracted_text(text)
    except ImportError:
        pass
    except Exception as e:
        print(f"[pypdf] Error reading PDF: {e}")

    if not text.strip():
        raise ValueError("Could not extract text from the PDF. The file may be scanned or image-based.")

    return _clean_extracted_text(text)


def _clean_extracted_text(text):
    """Clean and normalize extracted text."""
    import re
    # Remove null bytes and non-printable characters
    text = text.replace('\x00', '')
    text = re.sub(r'[^\x20-\x7E\n\r\t]', ' ', text)
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text