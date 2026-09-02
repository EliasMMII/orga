import sys

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4

import wca_common
import design_store


def generate_live_badges(competition_id, event_id, target_round, count_limit):
    print(f"Lade WCIF-Daten fuer '{competition_id}'...")

    try:
        wcif_data = wca_common.fetch_wcif(competition_id, timeout=10)
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

    namensschild_design = design_store.get_namensschild_design(competition_id)
    logo_path = namensschild_design.get("logo_path")
    logo_scale = namensschild_design.get("logo_scale", 1.0)

    output_pdf = f"Namenschilder_Live_{competition_id}_{round_id_str}_Top{count_limit}.pdf"
    page_size = landscape(A4)
    width, height = page_size
    c = canvas.Canvas(output_pdf, pagesize=page_size)

    print(f"Generiere {len(filtered_results)} Schilder fuer Top {count_limit} aus {round_id_str}...")

    for res in filtered_results:
        rank = res.get("ranking", 999)
        person_id = res.get("personId")
        competitor_name = name_map.get(person_id, f"Competitor #{person_id}")

        if wca_common.is_blind_event(event_id):
            raw_time = res.get("best", 0)
        else:
            raw_time = res.get("average", 0)
            if raw_time <= 0:
                raw_time = res.get("best", 0)

        formatted_time_str = wca_common.format_wca_time(raw_time, event_id)

        def draw_face(canvas_obj, name=competitor_name, rank=rank, time_str=formatted_time_str):
            wca_common.draw_badge_face(canvas_obj, name, event_id, rank, time_str, logo_path=logo_path, logo_scale=logo_scale)

        wca_common.render_badge_pair(c, width, height, draw_face)

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
