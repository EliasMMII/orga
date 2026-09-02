import os
import sys
import re
import base64

from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

import wca_common
import design_store


SVG_DIR = os.path.join("assets", "svgs")
OUTPUT_DIR = "Urkunden_Gesamt"
FONT_PATH = os.path.join("fonts", "GreatVibes-Regular.ttf")


if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont("GreatVibes", FONT_PATH))
else:
    print(f"WARNUNG: Schriftart '{FONT_PATH}' nicht gefunden.")


def clean_name(name):
    """Entfernt Klammern und den Inhalt darin aus dem Namen und bereinigt Leerzeichen."""
    if not name:
        return ""
    # Entfernt alles von '(' bis ')' inklusive der Klammern selbst
    cleaned = re.sub(r'\s*\(.*?\)', '', name)
    return cleaned.strip()


def get_competition_data(competition_id, event_id):
    print(f"Lade Daten für Competition '{competition_id}'...")

    try:
        wcif_data = wca_common.fetch_wcif(competition_id)
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

    try:
        live_data = wca_common.fetch_live_round_results(
            competition_id,
            wcif_data.get("name", competition_id),
            event_id
        )
    except Exception as e:
        live_data = None
        print(f"Hinweis: WCA Live nicht erreichbar ({e}), nutze WCA-Ergebnisse.")

    if live_data:
        live_results, round_finished = live_data

        if live_results:
            print("Nutze Live-Ergebnisse von WCA Live (aktueller als die WCA-Synchronisierung).")

            results = []

            for live_result in live_results:
                person = live_result.get("person") or {}
                person_id = person.get("registrantId")

                results.append({
                    "ranking": live_result.get("ranking"),
                    "personId": person_id,
                    "best": live_result.get("best"),
                    "average": live_result.get("average")
                })

                if person_id is not None:
                    persons[person_id] = {
                        "name": clean_name(person.get("name", "Unbekannt")),
                        "country": (person.get("country") or {}).get("iso2"),
                        "wca_id": person.get("wcaId")
                    }

            if not round_finished:
                print("WARNUNG: Die Runde ist laut WCA Live noch nicht als abgeschlossen markiert.")

    entries = []

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

        if wca_common.is_blind_event(event_id):
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
            "result": wca_common.format_wca_time(raw_result, event_id, mbf_order="certificate"),
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


def _recolor_drawing(node, color):
    """Überschreibt rekursiv alle gesetzten Füll-/Strichfarben eines
    svglib-Drawings mit einer einheitlichen Farbe (einfaches Icon-Recolor)."""
    if getattr(node, "fillColor", None) is not None:
        node.fillColor = color

    if getattr(node, "strokeColor", None) is not None:
        node.strokeColor = color

    for child in getattr(node, "contents", []):
        _recolor_drawing(child, color)


def draw_event_logo(c, event_id, center_x, center_y, size=30, color=None):
    svg_path = os.path.join(SVG_DIR, f"{event_id}.svg")

    if not os.path.exists(svg_path):
        print(f"WARNUNG: Event-Logo nicht gefunden: {svg_path}")
        return

    try:
        drawing = svg2rlg(svg_path)

        if not drawing:
            return

        if color:
            _recolor_drawing(drawing, colors.HexColor(color))

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


def _safe_set_font(c, font_name, font_size):
    """Setzt die Schriftart, fällt bei nicht registrierten Schriften (z. B.
    fehlende GreatVibes-Datei) auf Times-Roman zurück."""
    try:
        c.setFont(font_name, font_size)
        return font_name
    except KeyError:
        c.setFont("Times-Roman", font_size)
        return "Times-Roman"


def _default_result_label(event_id):
    if event_id in ("333bf", "444bf", "555bf"):
        return "mit einer Zeit von:"
    if event_id == "333mbf":
        return "mit einem Ergebnis von:"
    return "mit einem Durchschnitt von:"


def render_urkunde_overlay(design, context):
    """Rendert eine Urkunden-Seite (Overlay) anhand eines frei gestalteten
    Design-Entwurfs (design_store.get_urkunde_design: page, background,
    layers) und der dynamischen Werte in context (name, rank, event,
    event_id, competition, result).

    Layer-Koordinaten (x/y/width/height) sind wie im Canvas-Editor von der
    linken oberen Seitenecke aus gemessen (y wächst nach unten) und werden
    hier ins PDF-Koordinatensystem (Ursprung unten links) umgerechnet.
    """
    packet = BytesIO()

    page = design.get("page") or {}
    page_width = page.get("width", 595.5)
    page_height = page.get("height", 842.25)

    c = canvas.Canvas(packet, pagesize=(page_width, page_height))

    background = design.get("background") or {}

    if background.get("type") == "image":
        # "data" sind rohe Bild-Bytes (z. B. für eine Live-Vorschau ohne
        # Festplatten-Umweg), "path" ein gespeicherter Hintergrund.
        image_source = background.get("data")

        if image_source is None and background.get("path") and os.path.exists(background["path"]):
            image_source = background["path"]

        if image_source is not None:
            try:
                source = ImageReader(BytesIO(image_source)) if isinstance(image_source, (bytes, bytearray)) else image_source

                c.drawImage(
                    source, 0, 0,
                    width=page_width, height=page_height,
                    preserveAspectRatio=False, mask='auto'
                )
            except Exception as e:
                print(f"WARNUNG: Hintergrundbild konnte nicht geladen werden: {e}")

    event_id = context.get("event_id", "")
    context = dict(context)
    context.setdefault("result_label", _default_result_label(event_id))

    for layer in design.get("layers", []):
        layer_type = layer.get("type")
        x = layer.get("x", 0)
        y = layer.get("y", 0)
        width = layer.get("width", 0)
        height = layer.get("height", 0)
        angle = layer.get("angle", 0) or 0

        box_center_x = x + width / 2
        box_center_y_pdf = page_height - y - height / 2

        if layer_type == "event_logo":
            size = max(width, height) or 26
            draw_event_logo(c, event_id, box_center_x, box_center_y_pdf, size, color=layer.get("color"))
            continue

        if layer_type == "image":
            image_source = None

            if layer.get("path") and os.path.exists(layer["path"]):
                image_source = layer["path"]
            elif str(layer.get("src", "")).startswith("data:"):
                try:
                    _, encoded = layer["src"].split(",", 1)
                    image_source = ImageReader(BytesIO(base64.b64decode(encoded)))
                except Exception:
                    image_source = None

            if image_source is None:
                continue

            try:
                c.saveState()
                c.translate(box_center_x, box_center_y_pdf)
                if angle:
                    c.rotate(-angle)
                c.drawImage(
                    image_source, -width / 2, -height / 2,
                    width=width, height=height, mask='auto'
                )
                c.restoreState()
            except Exception as e:
                print(f"WARNUNG: Bild-Layer konnte nicht geladen werden: {e}")

            continue

        if layer_type != "text":
            continue

        try:
            text = (layer.get("content") or "").format(**context)
        except Exception:
            text = layer.get("content") or ""

        if not text:
            continue

        font_name = layer.get("font", "Times-Roman")
        font_size = layer.get("size", 20)
        align = layer.get("align", "left")

        # Grobe Näherung der Schrift-Oberkante, da Browser (Canvas-Editor)
        # und reportlab (PDF) Text unterschiedlich vermessen - die "Vorschau
        # aktualisieren"-Funktion zeigt das exakte PDF-Ergebnis.
        ascent = font_size * 0.8
        baseline_pdf_y = page_height - y - ascent

        anchor_x = x
        if align == "center":
            anchor_x = x + width / 2
        elif align == "right":
            anchor_x = x + width

        _safe_set_font(c, font_name, font_size)
        c.setFillColor(colors.HexColor(layer.get("color", "#000000")))

        c.saveState()
        c.translate(box_center_x, box_center_y_pdf)
        if angle:
            c.rotate(-angle)
        c.translate(anchor_x - box_center_x, baseline_pdf_y - box_center_y_pdf)

        if align == "center":
            c.drawCentredString(0, 0, text)
        elif align == "right":
            c.drawRightString(0, 0, text)
        else:
            c.drawString(0, 0, text)

        c.restoreState()

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
    print(f"GENERIERUNG FÜR: {wca_common.get_event_name(event_id)}")

    if country_code:
        print(f"Länderpodium: {country_code}")
    else:
        print("Gesamtpodium: Top 3")

    print(f"Anzahl Urkunden: {len(recipients)}")
    print("=" * 60)

    design = design_store.get_urkunde_design(competition_id)

    writer = PdfWriter()

    for entry in recipients:
        overlay_reader = render_urkunde_overlay(
            design,
            {
                "name": entry["name"],
                "rank": entry["certificate_rank"],
                "event": wca_common.get_event_name(event_id),
                "event_id": event_id,
                "competition": competition_name,
                "result": entry["result"]
            }
        )

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