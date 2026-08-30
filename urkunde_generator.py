import os
import sys
import requests
import re

from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF


# ==========================================
# KONFIGURATION FÜR DEN HINTERGRUND
# ==========================================
# True  = Nutzt das PDF-Template (TEMPLATE_PDF_PATH)
# False = Nutzt einen rein weißen Hintergrund
USE_TEMPLATE_PDF = False


TEMPLATE_PDF_PATH = os.path.join("assets", "Urkunde_leer.pdf")
SVG_DIR = os.path.join("assets", "svgs")
OUTPUT_DIR = "Urkunden_Gesamt"
FONT_PATH = os.path.join("fonts", "GreatVibes-Regular.ttf")


if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont("GreatVibes", FONT_PATH))
    NAME_FONT = "GreatVibes"
else:
    print(f"WARNUNG: Schriftart '{FONT_PATH}' nicht gefunden.")
    NAME_FONT = "Times-Italic"


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


def get_event_name(event_id):
    return EVENT_NAMES.get(event_id.lower(), event_id.upper())


def clean_name(name):
    """Entfernt Klammern und den Inhalt darin aus dem Namen und bereinigt Leerzeichen."""
    if not name:
        return ""
    # Entfernt alles von '(' bis ')' inklusive der Klammern selbst
    cleaned = re.sub(r'\s*\(.*?\)', '', name)
    return cleaned.strip()


def format_wca_time(centiseconds, event_id):
    """Konvertiert WCA-Ergebnisse in ein lesbares Format."""
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

        return f"{solved}/{attempted} in {time_str}"

    seconds = centiseconds / 100.0

    if seconds >= 60:
        minutes = int(seconds // 60)
        rem_seconds = seconds % 60
        return f"{minutes}:{rem_seconds:05.2f}"

    return f"{seconds:.2f}"


def get_competition_data(competition_id, event_id):
    url = (
        f"https://worldcubeassociation.org/api/v0/"
        f"competitions/{competition_id}/wcif/public"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 WCA Certificate Generator"
    }

    print(f"Lade Daten für Competition '{competition_id}'...")

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        wcif_data = response.json()

    except Exception as e:
        print(f"FEHLER beim Laden der WCA-Daten: {e}")
        return None, None

    persons = {}

    for person in wcif_data.get("persons", []):
        person_id = person.get("registrantId")

        if person_id is not None:
            raw_name = person.get("name", "Unbekannt")
            persons[person_id] = {
                "name": clean_name(raw_name),  # Hier wird der Name direkt bereinigt
                "country": person.get("countryIso2"),
                "wca_id": person.get("wcaId")
            }

    event_data = None

    for event in wcif_data.get("events", []):
        if event.get("id") == event_id:
            event_data = event
            break

    if not event_data:
        print(f"FEHLER: Event '{event_id}' wurde nicht gefunden.")
        return None, None

    rounds = event_data.get("rounds", [])

    if not rounds:
        print(f"FEHLER: Keine Runden für Event '{event_id}' gefunden.")
        return None, None

    final_round = rounds[-1]
    results = final_round.get("results", [])

    entries = []

    blind_events = [
        "333bf",
        "444bf",
        "555bf",
        "333mbf"
    ]

    for result in results:
        ranking = result.get("ranking")

        if not ranking or ranking <= 0:
            continue

        person_id = result.get("personId")

        person = persons.get(
            person_id,
            {
                "name": f"Competitor {person_id}",
                "country": None,
                "wca_id": None
            }
        )

        if event_id in blind_events:
            raw_result = result.get("best", 0)
            result_type = "best"
        else:
            raw_result = result.get("average", 0)
            result_type = "average"

            if not raw_result or raw_result <= 0:
                raw_result = result.get("best", 0)
                result_type = "best"

        entries.append({
            "name": person["name"],
            "country": person["country"],
            "wca_id": person["wca_id"],
            "actual_rank": ranking,
            "result": format_wca_time(raw_result, event_id),
            "result_type": result_type
        })

    entries.sort(key=lambda x: x["actual_rank"])

    return wcif_data, entries


def get_recipients(entries, country_code=None):
    recipients = []

    if not country_code:
        for entry in entries:
            if entry["actual_rank"] <= 3:
                recipient = entry.copy()
                recipient["certificate_rank"] = entry["actual_rank"]
                recipients.append(recipient)

        return recipients

    country_code = country_code.upper()

    country_entries = [
        entry for entry in entries
        if entry["country"] == country_code
    ]

    country_podium = country_entries[:3]

    if not country_podium:
        print(f"Keine Teilnehmer aus '{country_code}' gefunden.")
        return []

    third_country_rank = country_podium[-1]["actual_rank"]

    for entry in entries:
        if entry["actual_rank"] > third_country_rank:
            break

        recipient = entry.copy()

        if entry["country"] == country_code:
            country_rank = next(
                i + 1
                for i, country_entry in enumerate(country_podium)
                if (
                    country_entry["wca_id"] == entry["wca_id"]
                    if entry["wca_id"]
                    else country_entry["name"] == entry["name"]
                )
            )

            recipient["certificate_rank"] = country_rank

        else:
            recipient["certificate_rank"] = entry["actual_rank"]

        recipients.append(recipient)

    return recipients


def draw_centered_text(c, text, y, font_name, font_size):
    c.setFont(font_name, font_size)
    c.drawCentredString(595.5 / 2, y, text)


def draw_event_logo(c, event_id, center_x, center_y, size=30):
    svg_path = os.path.join(SVG_DIR, f"{event_id}.svg")

    if not os.path.exists(svg_path):
        print(f"WARNUNG: Event-Logo nicht gefunden: {svg_path}")
        return

    try:
        drawing = svg2rlg(svg_path)

        if not drawing:
            return

        scale = min(
            size / drawing.width,
            size / drawing.height
        )

        drawing.scale(scale, scale)

        width = drawing.width * scale
        height = drawing.height * scale

        renderPDF.draw(
            drawing,
            c,
            center_x - width / 2,
            center_y - height / 2
        )

    except Exception as e:
        print(f"WARNUNG: Event-Logo konnte nicht geladen werden: {e}")


def create_overlay_pdf(
    name,
    competition_name,
    event_id,
    certificate_rank,
    result
):
    packet = BytesIO()

    page_width = 595.5
    page_height = 842.25

    c = canvas.Canvas(
        packet,
        pagesize=(page_width, page_height)
    )

    c.setFillColor(colors.HexColor("#161616"))

    max_name_width = 470
    name_font_size = 48
    min_name_font_size = 28

    while (
        c.stringWidth(name, NAME_FONT, name_font_size)
        > max_name_width
        and name_font_size > min_name_font_size
    ):
        name_font_size -= 1

    draw_centered_text(
        c,
        name,
        445,
        NAME_FONT,
        name_font_size
    )

    draw_centered_text(
        c,
        "zum",
        397,
        "Times-Roman",
        20
    )

    draw_centered_text(
        c,
        f"{certificate_rank}. PLATZ",
        335,
        "Times-Roman",
        31
    )

    event_name = get_event_name(event_id)
    event_text = f"in {event_name}"
    event_font_size = 22

    c.setFont("Times-Roman", event_font_size)

    text_width = c.stringWidth(
        event_text,
        "Times-Roman",
        event_font_size
    )

    logo_size = 26
    logo_gap = 8

    total_width = text_width + logo_gap + logo_size
    start_x = (page_width - total_width) / 2

    c.drawString(
        start_x,
        273,
        event_text
    )

    draw_event_logo(
        c,
        event_id,
        start_x + text_width + logo_gap + logo_size / 2,
        281,
        logo_size
    )

    competition_prefix = "bei den "
    competition_font_size = 21

    c.setFont(
        "Times-Roman",
        competition_font_size
    )

    prefix_width = c.stringWidth(
        competition_prefix,
        "Times-Roman",
        competition_font_size
    )

    c.setFont(
        "Times-Bold",
        competition_font_size
    )

    competition_width = c.stringWidth(
        competition_name,
        "Times-Bold",
        competition_font_size
    )

    total_width = prefix_width + competition_width
    start_x = (page_width - total_width) / 2

    c.setFont(
        "Times-Roman",
        competition_font_size
    )

    c.drawString(
        start_x,
        223,
        competition_prefix
    )

    c.setFont(
        "Times-Bold",
        competition_font_size
    )

    c.drawString(
        start_x + prefix_width,
        223,
        competition_name
    )

    if event_id in ["333bf", "444bf", "555bf"]:
        result_label = "mit einer Zeit von:"
    elif event_id == "333mbf":
        result_label = "mit einem Ergebnis von:"
    else:
        result_label = "mit einem Durchschnitt von:"

    draw_centered_text(
        c,
        result_label,
        179,
        "Times-Roman",
        20
    )

    if event_id == "333mbf":
        result_text = result
    else:
        result_text = f"{result}"

    draw_centered_text(
        c,
        result_text,
        133,
        "Times-Roman",
        20
    )

    c.save()
    packet.seek(0)

    return PdfReader(packet)


def main():
    if len(sys.argv) not in [3, 4]:
        print()
        print("FEHLER: Ungültige Parameteranzahl.")
        print()
        print("Syntax ohne Länderpodium:")
        print("python urkunde_generator.py <CompetitionID> <EventID>")
        print()
        print("Syntax mit Länderpodium:")
        print("python urkunde_generator.py <CompetitionID> <EventID> <Land>")
        print()
        print("Beispiele:")
        print("python urkunde_generator.py RubiksGermanNationals2026 444")
        print("python urkunde_generator.py RubiksGermanNationals2026 444 DE")
        print()
        return

    competition_id = sys.argv[1]
    event_id = sys.argv[2].lower()

    country_code = None

    if len(sys.argv) == 4:
        country_code = sys.argv[3].upper()

    if USE_TEMPLATE_PDF and not os.path.exists(TEMPLATE_PDF_PATH):
        print(
            f"FEHLER: Vorlage nicht gefunden: {TEMPLATE_PDF_PATH}"
        )
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    wcif_data, entries = get_competition_data(
        competition_id,
        event_id
    )

    if not wcif_data or not entries:
        print("Keine gültigen Ergebnisse gefunden.")
        return

    competition_name = wcif_data.get(
        "name",
        competition_id
    )

    recipients = get_recipients(
        entries,
        country_code
    )

    if not recipients:
        print("Keine Urkundenempfänger gefunden.")
        return

    print()
    print("=" * 60)
    print(f"GENERIERUNG FÜR: {get_event_name(event_id)}")

    if country_code:
        print(f"Länderpodium: {country_code}")
    else:
        print("Gesamtpodium: Top 3")

    print(f"Anzahl Urkunden: {len(recipients)}")
    print("=" * 60)

    writer = PdfWriter()

    for entry in recipients:
        overlay_reader = create_overlay_pdf(
            name=entry["name"],
            competition_name=competition_name,
            event_id=event_id,
            certificate_rank=entry["certificate_rank"],
            result=entry["result"]
        )

        if USE_TEMPLATE_PDF:
            template_reader = PdfReader(TEMPLATE_PDF_PATH)
            page = template_reader.pages[0]
            page.merge_page(overlay_reader.pages[0])
            writer.add_page(page)
        else:
            writer.add_page(overlay_reader.pages[0])

        print(
            f"✓ {entry['name']} | "
            f"echter Platz: {entry['actual_rank']} | "
            f"Urkundenplatz: {entry['certificate_rank']} | "
            f"{entry['country']} | "
            f"{entry['result']}"
        )

    country_suffix = ""

    if country_code:
        country_suffix = f"_{country_code}"

    output_path = os.path.join(
        OUTPUT_DIR,
        f"Urkunden_{event_id.upper()}{country_suffix}.pdf"
    )

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    print()
    print("=" * 60)
    print("FERTIG!")
    print(f"Datei erstellt: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()