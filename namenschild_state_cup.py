import os

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors

from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

import wca_common

BUNDESLAND_FILE = os.path.join("assets", "bundesland_de.txt")


def draw_state_badge_face(c, state_name):
    # 2 cm nach rechts gerückt: Start von -400.0 auf -343.3 (20 mm = ~56.7 Punkte)
    box_start_x = -343.3

    comp_logo_start_x = wca_common.draw_competition_logo(c)

    box_width = comp_logo_start_x - box_start_x - 20.0

    # Bindestriche durch ein geschütztes Trennzeichen ersetzen, damit ReportLab umbrechen darf
    formatted_name = state_name.replace("-", "-<br/>")

    # Schriftgröße um 20% erhöht von 60 auf 72
    current_font_size = 72

    # Ermittle die Wörter für die Breitenprüfung (Bindestriche trennen jetzt das Wort)
    words = state_name.replace("-", " ").split()

    while current_font_size > 20:
        longest_word_width = max(c.stringWidth(w, "Helvetica-Bold", current_font_size) for w in words)
        if longest_word_width <= box_width:
            break
        current_font_size -= 1

    styles = getSampleStyleSheet()
    state_style = ParagraphStyle(
        'StateNameStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=current_font_size,
        leading=current_font_size + 4,
        alignment=0,
        textColor=colors.black
    )
    state_paragraph = Paragraph(formatted_name, state_style)

    state_table = Table([[state_paragraph]], colWidths=[box_width], rowHeights=140)
    state_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    state_table.wrapOn(c, box_width, 140)
    state_table.drawOn(c, box_start_x, -70)


def generate_state_badges():
    if not os.path.exists(BUNDESLAND_FILE):
        print(f"Fehler: Die Datei '{BUNDESLAND_FILE}' wurde nicht gefunden!")
        return

    with open(BUNDESLAND_FILE, 'r', encoding='utf-8') as f:
        states = [line.strip() for line in f if line.strip()]

    if not states:
        print("Fehler: Die Bundeslaender-Datei ist leer.")
        return

    output_pdf = "Namenschilder_Bundeslaender.pdf"
    print(f"Generiere Namensschilder fuer {len(states)} Bundeslaender...")

    page_size = landscape(A4)
    width, height = page_size
    c = canvas.Canvas(output_pdf, pagesize=page_size)

    for state in states:
        def draw_face(canvas_obj, state=state):
            draw_state_badge_face(canvas_obj, state)

        wca_common.render_badge_pair(c, width, height, draw_face)

    c.save()
    print(f"PDF erfolgreich gespeichert unter: {output_pdf}")


if __name__ == "__main__":
    generate_state_badges()
