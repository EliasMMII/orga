import os
from datetime import date, timedelta
from io import BytesIO

import requests
from PIL import Image
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


WCA_API_BASE = "https://worldcubeassociation.org/api/v0"
WCA_LIVE_API = "https://live.worldcubeassociation.org/api"

EVENT_NAMES = {
    "333": "3x3",
    "222": "2x2",
    "444": "4x4",
    "555": "5x5",
    "666": "6x6",
    "777": "7x7",
    "333bf": "3x3 Blind",
    "333fm": "Fewest Moves",
    "333oh": "3x3 One-Handed",
    "clock": "Clock",
    "minx": "Megaminx",
    "pyram": "Pyraminx",
    "skewb": "Skewb",
    "sq1": "Square-1",
    "444bf": "4x4 Blind",
    "555bf": "5x5 Blind",
    "333mbf": "3x3 Multi-Blind"
}

BLIND_EVENTS = {"333bf", "444bf", "555bf", "333mbf"}


def get_event_name(event_id):
    return EVENT_NAMES.get(event_id.lower(), event_id.upper())


def is_blind_event(event_id):
    return event_id in BLIND_EVENTS


def format_wca_time(centiseconds, event_id, mbf_order="badge"):
    """Konvertiert WCA-Ergebnisse (Centiseconds) in ein lesbares Format.

    mbf_order steuert bei 3x3 Multi-Blind die Reihenfolge der Anzeige:
    "badge" -> "12:34 5/7" (Namensschilder), "certificate" -> "5/7 in 12:34" (Urkunden).
    """
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

        if mbf_order == "certificate":
            return f"{solved}/{attempted} in {time_str}"
        return f"{time_str} {solved}/{attempted}"

    seconds = centiseconds / 100.0

    if seconds >= 60:
        minutes = int(seconds // 60)
        rem_seconds = seconds % 60
        return f"{minutes}:{rem_seconds:05.2f}"

    return f"{seconds:.2f}"


def fetch_wcif(competition_id, timeout=20):
    """Lädt die öffentlichen WCIF-Daten einer Competition von der WCA-API."""
    url = f"{WCA_API_BASE}/competitions/{competition_id}/wcif/public"
    headers = {"User-Agent": "Mozilla/5.0 WCA Generator"}

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    return response.json()


def fetch_ongoing_competitions(lookback_days=10, timeout=15):
    """Lädt alle aktuell laufenden Competitions (heutiges Datum liegt zwischen
    Start- und Enddatum) von der öffentlichen WCA-API.

    Die WCA-API filtert nur nach dem Startdatum, daher wird hier ein
    Zeitfenster von lookback_days vor heute abgefragt (Competitions dauern
    praktisch nie länger) und anschließend clientseitig auf 'läuft noch'
    (end_date >= heute) sowie 'nicht abgesagt' gefiltert.
    """
    today = date.today()
    window_start = today - timedelta(days=lookback_days)

    headers = {"User-Agent": "Mozilla/5.0 WCA Generator"}
    params = {
        "start": window_start.isoformat(),
        "end": today.isoformat(),
        "sort": "start_date"
    }

    url = f"{WCA_API_BASE}/competitions"
    competitions = []

    while url:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        competitions.extend(response.json())

        # Die Query-Parameter stecken ab der zweiten Seite bereits in der
        # vom Server gelieferten Link-Header-URL.
        params = None
        next_link = response.links.get("next")
        url = next_link.get("url") if next_link else None

    today_str = today.isoformat()

    ongoing = [
        comp for comp in competitions
        if comp.get("end_date", "") >= today_str and not comp.get("cancelled_at")
    ]

    ongoing.sort(key=lambda comp: comp.get("start_date", ""))

    return ongoing


def _wca_live_request(query, variables=None, timeout=15):
    """Führt eine GraphQL-Anfrage gegen die WCA-Live-API aus.

    WCA Live hat eine eigene Datenbank, die per Hintergrund-Sync mit der
    öffentlichen WCA-API (fetch_wcif) abgeglichen wird. Dieser Sync kann
    mehrere Minuten dauern, weshalb frisch eingetragene Ergebnisse in
    fetch_wcif() teils erst deutlich verzögert auftauchen. Über diese
    Funktion lassen sich Ergebnisse direkt aus WCA Live abfragen, ohne
    auf den Sync zu warten.
    """
    response = requests.post(
        WCA_LIVE_API,
        json={"query": query, "variables": variables or {}},
        headers={"Content-Type": "application/json"},
        timeout=timeout
    )
    response.raise_for_status()

    payload = response.json()

    if "errors" in payload:
        raise RuntimeError(payload["errors"][0].get("message", "WCA Live GraphQL Fehler"))

    return payload.get("data") or {}


def _find_wca_live_competition_id(competition_id, name_hint):
    """Sucht die interne WCA-Live-ID einer Competition anhand ihrer WCA-ID.

    WCA Live kennt Competitions nur unter einer eigenen numerischen ID, nicht
    unter der WCA-ID (z. B. 'RubiksGermanNationals2026'). Der Name der
    Competition dient hier nur als Textfilter, um die Trefferliste klein zu
    halten - der eigentliche Abgleich erfolgt über die exakte WCA-ID.
    """
    query = """
        query($filter: String, $limit: Int) {
            competitions(filter: $filter, limit: $limit) {
                id
                wcaId
            }
        }
    """

    data = _wca_live_request(query, {"filter": name_hint, "limit": 25})

    for competition in data.get("competitions", []):
        if competition.get("wcaId") == competition_id:
            return competition.get("id")

    return None


def fetch_live_round_results(competition_id, competition_name, event_id):
    """Lädt die Ergebnisse der letzten (finalen) Runde eines Events direkt aus
    WCA Live, ohne die Synchronisationsverzögerung zur öffentlichen WCA-API.

    Gibt (results, finished) zurück - results im WCA-Live-Format (ranking,
    best, average, person{...}) - oder None, wenn die Competition oder das
    Event auf WCA Live nicht gefunden werden konnte.
    """
    live_competition_id = _find_wca_live_competition_id(competition_id, competition_name)

    if not live_competition_id:
        return None

    events_query = """
        query($id: ID!) {
            competition(id: $id) {
                competitionEvents {
                    event { id }
                    rounds { id number }
                }
            }
        }
    """

    events_data = _wca_live_request(events_query, {"id": live_competition_id})
    competition = events_data.get("competition")

    if not competition:
        return None

    target_rounds = []

    for competition_event in competition.get("competitionEvents", []):
        if (competition_event.get("event") or {}).get("id") == event_id:
            target_rounds = competition_event.get("rounds", [])
            break

    if not target_rounds:
        return None

    final_round = max(target_rounds, key=lambda r: r.get("number", 0))

    round_query = """
        query($id: ID!) {
            round(id: $id) {
                finished
                results {
                    ranking
                    best
                    average
                    person {
                        name
                        wcaId
                        registrantId
                        country { iso2 }
                    }
                }
            }
        }
    """

    round_data = _wca_live_request(round_query, {"id": final_round["id"]})
    round_info = round_data.get("round")

    if not round_info:
        return None

    return round_info.get("results", []), round_info.get("finished", False)


def draw_competition_logo(c, logo_path=None, scale=1.0):
    """Zeichnet das Wettkampf-Logo und gibt dessen linke X-Koordinate zurück.

    logo_path ist entweder ein Dateipfad (Standard: assets/Logo.png), oder
    rohe Bild-Bytes (z. B. eine hochgeladene Datei aus der Design-Vorschau,
    ohne Umweg über die Festplatte). scale skaliert die Standardgröße des
    Logos (1.0 = Standardgröße, z. B. 1.5 = 150%).
    """
    is_bytes = isinstance(logo_path, (bytes, bytearray))

    if logo_path is None:
        logo_path = os.path.join("assets", "Logo.png")

    comp_logo_start_x = 129

    if not is_bytes and not os.path.exists(logo_path):
        return comp_logo_start_x

    target_height = 208.3 * (scale or 1.0)

    try:
        image_source = ImageReader(BytesIO(logo_path)) if is_bytes else logo_path

        with Image.open(BytesIO(logo_path) if is_bytes else logo_path) as img:
            orig_width, orig_height = img.size

        target_width = (orig_width / orig_height) * target_height
        comp_logo_start_x = 400.0 - target_width

        c.drawImage(
            image_source, comp_logo_start_x, -(target_height / 2),
            width=target_width, height=target_height, mask='auto'
        )
    except Exception:
        target_width = 340 * (scale or 1.0)
        comp_logo_start_x = 400.0 - target_width
        image_source = ImageReader(BytesIO(logo_path)) if is_bytes else logo_path

        c.drawImage(
            image_source, comp_logo_start_x, -(target_height / 2),
            width=target_width, height=target_height, mask='auto'
        )

    return comp_logo_start_x


def draw_badge_face(c, name, event_id, rank_number, displayed_time_str, logo_path=None, logo_scale=1.0):
    """Zeichnet eine Namensschild-Seite: Event-Logo, Rang, Zeit, Name und Wettkampf-Logo.

    logo_path überschreibt optional das Standard-Wettkampf-Logo (assets/Logo.png),
    z. B. für ein pro Competition hochgeladenes Logo. logo_scale skaliert dessen
    Größe (1.0 = Standard).
    """
    logo_start_x = -400
    event_logo_size = 105.0
    gap_between = 15.0
    font_name = "Helvetica-Bold"
    font_size_rank = 98

    comp_logo_start_x = draw_competition_logo(c, logo_path=logo_path, scale=logo_scale)

    svg_path = os.path.join("assets", "svgs", f"{event_id}.svg")
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
        longest_word_width = max(c.stringWidth(w, "Helvetica-Bold", current_font_size) for w in words)
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
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    name_table.wrapOn(c, box_width, 140)
    name_table.drawOn(c, box_start_x, -70)


def render_badge_pair(c, width, height, draw_face):
    """Zeichnet Vorder- und um 180° gedrehte Rückseite eines Namensschilds
    auf eine A4-Querseite (draw_face(c) zeichnet jeweils eine Seite) und schließt die Seite ab."""
    c.saveState()
    c.translate(width / 2, height * 0.25)
    draw_face(c)
    c.restoreState()

    c.saveState()
    c.translate(width / 2, height * 0.75)
    c.rotate(180)
    draw_face(c)
    c.restoreState()

    c.setStrokeColor(colors.gray)
    c.setLineWidth(1)
    c.setDash(6, 3)
    c.line(0, height / 2, width, height / 2)
    c.showPage()
