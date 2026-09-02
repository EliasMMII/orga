import sys

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4

import wca_common
import design_store


def get_personal_best_single_raw(participant, event_id):
    for pb in participant.get("personalBests", []):
        if pb.get("eventId") == event_id and pb.get("type") == "single":
            return pb.get("best", 99999999)
    return 99999999


def get_personal_best_average_raw(participant, event_id):
    for pb in participant.get("personalBests", []):
        if pb.get("eventId") == event_id and pb.get("type") == "average":
            return pb.get("best", 99999999)
    return 99999999


def get_sorting_tuple(participant, event_id):
    single = get_personal_best_single_raw(participant, event_id)
    average = get_personal_best_average_raw(participant, event_id)

    if wca_common.is_blind_event(event_id):
        category = 0 if single != 99999999 else 1
        return (category, single, 99999999)

    if average != 99999999:
        return (0, average, single)
    if single != 99999999:
        return (1, single, single)
    return (2, 99999999, 99999999)


def get_ranked_competitors(wcif_data, event_id):
    """Sortiert alle akzeptierten Teilnehmer eines Events nach ihrem WCA-Seeding (Personal Best)."""
    competitors = [
        person for person in wcif_data.get("persons", [])
        if (
            person.get("registration")
            and person["registration"].get("status") == "accepted"
            and event_id in person["registration"].get("eventIds", [])
        )
    ]

    competitors.sort(key=lambda person: get_sorting_tuple(person, event_id))

    return competitors


def generate_round1_badges(wcif_data, event_id, output_pdf=None):
    """Erzeugt Namensschilder für Runde 1, sortiert nach Anmelde-Seeding (Personal Best)."""
    competitors = get_ranked_competitors(wcif_data, event_id)

    if not competitors:
        print(f"Keine akzeptierten Teilnehmer fuer das Event '{event_id}' gefunden.")
        return None

    comp_id = wcif_data.get("id", "Competition")

    if output_pdf is None:
        output_pdf = f"Namensschilder_{comp_id}_{event_id}_Runde1.pdf"

    namensschild_design = design_store.get_namensschild_design(comp_id)
    logo_path = namensschild_design.get("logo_path")
    logo_scale = namensschild_design.get("logo_scale", 1.0)

    print(f"Generiere {len(competitors)} Namensschilder fuer '{event_id}' (Runde 1, nach Seeding)...")

    page_size = landscape(A4)
    width, height = page_size
    c = canvas.Canvas(output_pdf, pagesize=page_size)

    current_rank = 1
    previous_sorting_value = None

    for index, participant in enumerate(competitors, start=1):
        sorting_value = get_sorting_tuple(participant, event_id)

        if sorting_value != previous_sorting_value:
            current_rank = index

        previous_sorting_value = sorting_value

        if wca_common.is_blind_event(event_id):
            raw_time = get_personal_best_single_raw(participant, event_id)
        else:
            raw_time = get_personal_best_average_raw(participant, event_id)
            if raw_time == 99999999:
                raw_time = get_personal_best_single_raw(participant, event_id)

        formatted_time_str = wca_common.format_wca_time(raw_time, event_id)
        name = participant.get("name", "Unknown Competitor")
        rank = current_rank

        def draw_face(canvas_obj, name=name, rank=rank, time_str=formatted_time_str):
            wca_common.draw_badge_face(canvas_obj, name, event_id, rank, time_str, logo_path=logo_path, logo_scale=logo_scale)

        wca_common.render_badge_pair(c, width, height, draw_face)

    c.save()
    print(f"PDF erfolgreich gespeichert unter: {output_pdf}")

    return output_pdf


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("\nFehler: Ungueltige Parameteranzahl!")
        print("Syntax: python namenschild_round1.py <CompetitionID> <EventID>")
        print("Beispiel: python namenschild_round1.py CapelleChaosB2026 333\n")
    else:
        comp_id = sys.argv[1]
        chosen_event = sys.argv[2].lower()

        try:
            wcif = wca_common.fetch_wcif(comp_id)
        except Exception as e:
            print(f"Fehler beim Laden der WCA-Daten: {e}")
        else:
            generate_round1_badges(wcif, chosen_event)
