import os
import sys
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from PIL import Image

from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def format_wca_time(centiseconds, event_id):
    """Konvertiert WCA-Ergebnisse in ein lesbares Format ohne Einheiten."""
    if not centiseconds or centiseconds == 99999999:
        return "Newcomer"
        
    if event_id == "333mbf":
        val_str = str(centiseconds).zfill(9)
        points_diff = 99 - int(val_str[0:2])
        time_seconds = int(val_str[2:7])
        missed = int(val_str[7:9])
        
        solved = points_diff + missed
        attempted = solved + missed
        
        if time_seconds == 99999:
            time_str = "N/A"
        else:
            hours = time_seconds // 3600
            minutes = (time_seconds % 3600) // 60
            seconds = time_seconds % 60
            if hours > 0:
                time_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                time_str = f"{minutes:02d}:{seconds:02d}"
                
        return f"{time_str} {solved}/{attempted}"
        
    seconds = centiseconds / 100.0
    if seconds >= 60:
        minutes = int(seconds // 60)
        rem_seconds = seconds % 60
        return f"{minutes}:{rem_seconds:05.2f}"
    return f"{seconds:.2f}"

def is_blind_event(event_id):
    return event_id in ["333bf", "444bf", "555bf", "333mbf"]

def get_personal_best_single_raw(participant, event_id):
    bests = participant.get("personalBests", [])
    for pb in bests:
        if pb.get("eventId") == event_id and pb.get("type") == "single":
            return pb.get("best", 99999999)
    return 99999999

def get_personal_best_average_raw(participant, event_id):
    bests = participant.get("personalBests", [])
    for pb in bests:
        if pb.get("eventId") == event_id and pb.get("type") == "average":
            return pb.get("best", 99999999)
    return 99999999

def get_sorting_tuple(participant, event_id):
    single = get_personal_best_single_raw(participant, event_id)
    average = get_personal_best_average_raw(participant, event_id)
    
    if is_blind_event(event_id):
        category = 0 if single != 99999999 else 1
        return (category, single, 99999999)
    else:
        if average != 99999999:
            return (0, average, single)
        elif single != 99999999:
            return (1, single, single)
        else:
            return (2, 99999999, 99999999)

def draw_badge_face(c, participant, target_event, rank_number, displayed_time_str):
    logo_start_x = -400
    event_logo_size = 105.0
    gap_between = 15.0
    font_name = "Helvetica-Bold"
    font_size_rank = 98
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

    svg_path = os.path.join("assets", "svgs", f"{target_event}.svg")
    if os.path.exists(svg_path):
        try:
            drawing = svg2rlg(svg_path)
            scale_x = event_logo_size / drawing.width
            scale_y = event_logo_size / drawing.height
            drawing.scale(scale_x, scale_y)
            renderPDF.draw(drawing, c, logo_start_x, -52.5)
        except Exception:
            pass

    rank_str = str(rank_number)
    rank_x = logo_start_x + event_logo_size + gap_between
    c.setFont(font_name, font_size_rank)
    c.setFillColor(colors.HexColor("#D35400"))
    c.drawString(rank_x, -35, rank_str)

    rank_text_width = c.stringWidth(rank_str, font_name, font_size_rank)
    block_end_x = rank_x + rank_text_width
    
    dynamic_left_center_x = logo_start_x + ((block_end_x - logo_start_x) / 2)
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(colors.HexColor("#1A5276"))
    c.drawCentredString(dynamic_left_center_x, -95, displayed_time_str)

    box_start_x = block_end_x + 45.0
    box_width = comp_logo_start_x - box_start_x - 20.0
    
    name = participant.get("name", "Unknown Competitor")
    if "(" in name:
        name = name.split("(")[0].strip()
        
    words = name.split()
    current_font_size = 60
    
    while current_font_size > 20:
        longest_word_width = max([c.stringWidth(w, "Helvetica-Bold", current_font_size) for w in words])
        if longest_word_width <= box_width:
            break
        current_font_size -= 1

    styles = getSampleStyleSheet()
    name_style = ParagraphStyle(
        'BadgeNameStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=current_font_size,
        leading=current_font_size + 4, 
        alignment=0,
        textColor=colors.black
    )
    name_paragraph = Paragraph(name, name_style)
    
    name_table = Table([[name_paragraph]], colWidths=[box_width], rowHeights=140)
    name_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), 
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),   
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    
    name_table.wrapOn(c, box_width, 140)
    name_table.drawOn(c, box_start_x, -70)

def generate_badges(target_event):
    json_path = "competition_data.json"
    if not os.path.exists(json_path):
        print("Fehler: Die Datei 'competition_data.json' wurde nicht gefunden!")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        wca_data = json.load(f)
    
    all_persons = wca_data.get("persons", [])
    filtered_competitors = []
    for p in all_persons:
        reg = p.get("registration", {})
        if reg and reg.get("status") == "accepted":
            if target_event in reg.get("eventIds", []):
                filtered_competitors.append(p)
            
    if not filtered_competitors:
        print(f"Keine akzeptierten Teilnehmer fuer das Event '{target_event}' gefunden.")
        return

    filtered_competitors.sort(key=lambda x: get_sorting_tuple(x, target_event))
    
    comp_id = wca_data.get("id", "RubiksGermanNationals2026")
    output_pdf = f"Namensschilder_{comp_id}_{target_event}_Runde1.pdf"
    
    print(f"Generiere exakte WCA-Namensschilder fuer '{target_event}'...")
    page_size = landscape(A4)
    width, height = page_size
    c = canvas.Canvas(output_pdf, pagesize=page_size)
    
    current_rank = 1
    previous_sorting_value = None
    
    for index, participant in enumerate(filtered_competitors, start=1):
        sorting_value = get_sorting_tuple(participant, target_event)
        
        if previous_sorting_value is not None and sorting_value == previous_sorting_value:
            pass
        else:
            current_rank = index
            
        previous_sorting_value = sorting_value
        
        if is_blind_event(target_event):
            raw_time = get_personal_best_single_raw(participant, target_event)
        else:
            raw_time = get_personal_best_average_raw(participant, target_event)
            if raw_time == 99999999:
                raw_time = get_personal_best_single_raw(participant, target_event)

        formatted_time_str = format_wca_time(raw_time, target_event)

        c.saveState()
        c.translate(width / 2, height * 0.25)
        draw_badge_face(c, participant, target_event, current_rank, formatted_time_str)
        c.restoreState()

        c.saveState()
        c.translate(width / 2, height * 0.75)
        c.rotate(180)
        draw_badge_face(c, participant, target_event, current_rank, formatted_time_str)
        c.restoreState()

        c.setStrokeColor(colors.gray)
        c.setLineWidth(1)
        c.setDash(6, 3)
        c.line(0, height / 2, width, height / 2)
        c.showPage()
        
    c.save()
    print(f"PDF erfolgreich gespeichert unter: {output_pdf}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nFehler: Du musst ein Event angeben!")
        print("Beispiel: python namenschild_round1.py 333\n")
    else:
        chosen_event = sys.argv[1].lower()
        generate_badges(chosen_event)
