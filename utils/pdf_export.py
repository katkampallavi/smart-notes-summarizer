from reportlab.pdfgen import canvas
import os

def create_pdf(summary):

    download_folder = "static/downloads"

    os.makedirs(download_folder, exist_ok=True)

    pdf_file = os.path.join(
        download_folder,
        "summary.pdf"
    )

    c = canvas.Canvas(pdf_file)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(180, 800, "Smart Notes Summary")

    c.setFont("Helvetica", 12)

    y = 760

    words = summary.split()

    line = ""

    for word in words:

        if len(line + word) < 80:
            line += word + " "

        else:
            c.drawString(50, y, line)

            y -= 20

            line = word + " "

            if y < 50:
                c.showPage()
                c.setFont("Helvetica", 12)
                y = 800

    c.drawString(50, y, line)

    c.save()

    return pdf_file