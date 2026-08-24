import os
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

from request import get_competition_podiums


TEMPLATE_PDF_PATH = r"assets\Urkunde_leer.pdf"
OUTPUT_PDF_PATH = "Alle_Urkunden.pdf"


def create_overlay_pdf(
    name,
    event_id,
    rank,
    average_time
):

    packet = BytesIO()

    c = canvas.Canvas(
        packet,
        pagesize=(842.0, 595.0)
    )

    c.setFont(
        "Helvetica-Bold",
        28
    )

    c.setFillColor(
        colors.HexColor("#1e1e1e")
    )

    c.drawString(
        250,
        320,
        name
    )

    c.setFont(
        "Helvetica",
        18
    )

    c.drawString(
        250,
        270,
        f"Disziplin: {event_id.upper()} - {rank}. PLATZ"
    )

    c.setFont(
        "Helvetica",
        16
    )

    c.drawString(
        250,
        230,
        f"Durchschnitt: {average_time}"
    )

    c.save()

    packet.seek(0)

    return PdfReader(packet)


def main():

    competition_id = "SuperSideSummerFurth2026"

    if not os.path.exists(
        TEMPLATE_PDF_PATH
    ):

        print(
            f"FEHLER: Vorlage "
            f"'{TEMPLATE_PDF_PATH}' "
            f"nicht gefunden!"
        )

        return

    processed_data = get_competition_podiums(
        competition_id
    )

    if not processed_data:

        print(
            "Keine Daten erhalten."
        )

        return

    pdf_writer = PdfWriter()

    total_certificates = 0

    print()
    print(
        "=== GENERIERE URKUNDEN ==="
    )

    # -----------------------------------------
    # Events
    # -----------------------------------------

    for event_id, entries in (
        processed_data.items()
    ):

        entries.sort(
            key=lambda x: x["pos"]
        )

        # -------------------------------------
        # Top 3 insgesamt
        # -------------------------------------

        podium_overall = [
            entry
            for entry in entries
            if 1 <= entry["pos"] <= 3
        ]

        # -------------------------------------
        # Top 3 Deutsche
        # -------------------------------------

        german_results = [
            entry
            for entry in entries
            if entry["country"] == "DE"
        ]

        german_podium = (
            german_results[:3]
        )

        # -------------------------------------
        # Empfänger zusammenführen
        # -------------------------------------

        recipients = {}

        for entry in podium_overall:

            key = (
                entry["wca_id"]
                if entry["wca_id"]
                else entry["name"]
            )

            recipients[key] = entry

        for entry in german_podium:

            key = (
                entry["wca_id"]
                if entry["wca_id"]
                else entry["name"]
            )

            recipients[key] = entry

        print()
        print(
            f"{event_id.upper()}"
        )

        print(
            f"Gesamtpodium: "
            f"{len(podium_overall)}"
        )

        print(
            f"Deutsches Podium: "
            f"{len(german_podium)}"
        )

        # -------------------------------------
        # Urkunden erstellen
        # -------------------------------------

        for entry in recipients.values():

            name = entry["name"]
            position = entry["pos"]
            average = entry["average"]

            template_reader = PdfReader(
                TEMPLATE_PDF_PATH
            )

            page = template_reader.pages[0]

            overlay = create_overlay_pdf(
                name,
                event_id,
                position,
                average
            )

            page.merge_page(
                overlay.pages[0]
            )

            pdf_writer.add_page(
                page
            )

            total_certificates += 1

            print(
                f"✓ {name} "
                f"({entry['country']}) "
                f"- {position}. Platz "
                f"- Ø {average}"
            )

    # -----------------------------------------
    # PDF speichern
    # -----------------------------------------

    with open(
        OUTPUT_PDF_PATH,
        "wb"
    ) as f:

        pdf_writer.write(f)

    print()
    print(
        "=" * 60
    )

    print(
        f"Fertig!"
    )

    print(
        f"{total_certificates} Urkunden erstellt."
    )

    print(
        f"Datei: {OUTPUT_PDF_PATH}"
    )

    print(
        "=" * 60
    )


if __name__ == "__main__":
    main()