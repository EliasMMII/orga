import os
import sys
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from PIL import Image

from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def draw_state_badge_face(c, state_name):
    # 2 cm nach rechts gerückt: Start von -400.0 auf -343.3 (20 mm = ~56.7 Punkte)
    box_start_x = -343.3
    comp_logo_start_x = 129 

    comp_logo_path = os.path.join("assets", "Logo.png")
    if os.path.exists(comp_logo_path):
        try:
            with Image.open(comp_logo_path) as img:
                orig_width, orig_height = img.size
            target_height = 208.3
            target_width = (orig_width / orig_height) * target_height
            comp_logo_start_x = 400.0 - target_width
            c.drawImage(comp_logo_path, comp_logo_start_x, 0 - (target_height / 2),
                        width=target_width, height=target_height, mask='auto')
        except Exception:
            target_height = 208.3
            comp_logo_start_x = 400.0 - 340.0
            c.drawImage(comp_logo_path, comp_logo_start_x, 0 - (target_height / 2),
                        width=340, height=target_height, mask='auto')

    box_width = comp_logo_start_x - box_start_x - 20.0

    # Bindestriche durch ein geschütztes Trennzeichen ersetzen, damit ReportLab umbrechen darf
    formatted_name = state_name.replace("-", "-<br/>")

    # Schriftgröße um 20% erhöht von 60 auf 72
    base_font_size = 72
    current_font_size = base_font_size
    
    # Ermittle die Wörter für die Breitenprüfung (Bindestriche trennen jetzt das Wort)
    words = state_name.replace("-", " ").split()
    
    while current_font_size > 20:
        longest_word_width = max([c.stringWidth(w, "Helvetica-Bold", current_font_size) for w in words])
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
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))

    name_table = state_table
    name_table.wrapOn(c, box_width, 140)
    name_table.drawOn(c, box_start_x, -70)

def generate_state_badges():
    txt_path = r"C:\02Speedcubing\Orga\assets\bundesland_de.txt"
    if not os.path.exists(txt_path):
        print(f"Fehler: Die Datei '{txt_path}' wurde nicht gefunden!")
        return 

    with open(txt_path, 'r', encoding='utf-8') as f:
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
        c.saveState()
        c.translate(width / 2, height * 0.25)
        draw_state_badge_face(c, state)
        c.restoreState()

        c.saveState()
        c.translate(width / 2, height * 0.75)
        c.rotate(180)
        draw_state_badge_face(c, state)
        c.restoreState()

        c.setStrokeColor(colors.gray)
        c.setLineWidth(1)
        c.setDash(6, 3)
        c.line(0, height / 2, width, height / 2)
        c.showPage()

    c.save()
    print(f"PDF erfolgreich gespeichert unter: {output_pdf}")

if __name__ == "__main__":
    generate_state_badges()
