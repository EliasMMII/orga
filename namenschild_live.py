import os
import sys
import requests
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
    if not centiseconds or centiseconds == 99999999 or centiseconds <= 0:
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

def draw_badge_face(c, name, target_event, rank_number, displayed_time_str):
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

def generate_live_badges(competition_id, event_id, target_round, count_limit):
    # Exakter, korrekter API-Pfad mit allen notwendigen Slashes
    url = f"https://worldcubeassociation.org/api/v0/competitions/{competition_id}/wcif/public"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WCA-Orga-Script"}
    
    print(f"Lade WCIF-Daten von: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        wcif_data = response.json()
    except Exception as e:
        print(f"Fehler beim Laden der WCA-Daten: {e}")
        return

    target_event_data = None
    for e in wcif_data.get("events", []):
        if e.get("id") == event_id:
            target_event_data = e
            break
            
    if not target_event_data:
        print(f"Fehler: Event '{event_id}' nicht in der Competition gefunden.")
        return

    round_id_str = f"{event_id}-r{target_round}"
    selected_round = None
    for r in target_event_data.get("rounds", []):
        if r.get("id") == round_id_str:
            selected_round = r
            break
            
    if not selected_round:
        print(f"Fehler: Runde '{round_id_str}' wurde im WCIF nicht gefunden.")
        return

    round_results = selected_round.get("results", [])
    if not round_results:
        print(f"Fehler: Runde '{round_id_str}' enthaelt noch keine Ergebnisse.")
        return

    name_map = {}
    for p in wcif_data.get("persons", []):
        if p.get("registrantId") is not None:
            name_map[p.get("registrantId")] = p.get("name")

    filtered_results = round_results[:count_limit]
    
    output_pdf = f"Namenschilder_Live_{competition_id}_{round_id_str}_Top{count_limit}.pdf"
    page_size = landscape(A4)
    width, height = page_size
    c = canvas.Canvas(output_pdf, pagesize=page_size)
    
    print(f"Generiere {len(filtered_results)} Schilder fuer Top {count_limit} aus {round_id_str}...")

    for res in filtered_results:
        rank = res.get("ranking", 999)
        person_id = res.get("personId")
        competitor_name = name_map.get(person_id, f"Competitor #{person_id}")
        
        if is_blind_event(event_id):
            raw_time = res.get("best", 0)
        else:
            raw_time = res.get("average", 0)
            if raw_time <= 0:
                raw_time = res.get("best", 0)
                
        formatted_time_str = format_wca_time(raw_time, event_id)

        c.saveState()
        c.translate(width / 2, height * 0.25)
        draw_badge_face(c, competitor_name, event_id, rank, formatted_time_str)
        c.restoreState()

        c.saveState()
        c.translate(width / 2, height * 0.75)
        c.rotate(180)
        draw_badge_face(c, competitor_name, event_id, rank, formatted_time_str)
        c.restoreState()

        c.setStrokeColor(colors.gray)
        c.setLineWidth(1)
        c.setDash(6, 3)
        c.line(0, height / 2, width, height / 2)
        c.showPage()
        
    c.save()
    print(f"PDF erfolgreich gespeichert unter: {output_pdf}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("\nFehler: Ungueltige Parameteranzahl!")
        print("Syntax: python namenschild_live.py <CompID> <Event> <Runde> <Anzahl>")
        print("Beispiel: python namenschild_live.py CapelleChaosB2026 333 1 16\n")
    else:
        comp = sys.argv[1]
        event = sys.argv[2].lower()
        try:
            r_num = int(sys.argv[3])
            limit = int(sys.argv[4])
            generate_live_badges(comp, event, r_num, limit)
        except ValueError:
            print("Fehler: Runde und Anzahl muessen ganzzahlige Nummern sein!")
