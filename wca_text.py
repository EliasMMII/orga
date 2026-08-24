import requests
import json

def fetch_wca_wcif_ranking(competition_id, event_id="333"):
    # Der offizielle oeffentliche WCIF-Endpunkt der WCA
    url = f"https://www.worldcubeassociation.org/api/v0/competitions/{competition_id}/wcif/public"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WCA-Orga-Script"
    }
    
    print(f"Lade oeffentliche WCIF-Daten fuer '{competition_id}' von der WCA-Plattform...")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        wcif_data = response.json()
        
        # 1. Schritt: Finde das richtige Event im WCIF
        events = wcif_data.get("events", [])
        target_event = None
        for e in events:
            if e.get("id") == event_id:
                target_event = e
                break
                
        if not target_event:
            print(f"Fehler: Das Event '{event_id}' wurde in dieser Competition nicht gefunden.")
            return

        # 2. Schritt: Finde die aktuellste Runde dieses Events
        rounds = target_event.get("rounds", [])
        if not rounds:
            print(f"Fehler: Keine Runden fuer das Event '{event_id}' angelegt.")
            return
            
        # Die Runden sind im WCIF chronologisch benannt (z.B. '333-r1', '333-r2')
        # Wir sortieren nach der Rundennummer am Ende der ID
        latest_round = max(rounds, key=lambda r: int(r.get("id").split("-r")[-1]))
        round_id_str = latest_round.get("id")
        
        # 3. Schritt: Ergebnisse (Results) dieser Runde sammeln
        round_results = latest_round.get("results", [])
        if not round_results:
            print(f"Hinweis: Die Runde '{round_id_str}' existiert, enthaelt aber noch keine Ergebnisse.")
            return

        # Da im WCIF-Resultat meistens nur die 'personId' (Registrierungs-ID) steht,
        # bauen wir uns ein Map-Verzeichnis auf, um die Klarnamen der Personen zuzuordnen.
        persons_list = wcif_data.get("persons", [])
        name_map = {}
        for p in persons_list:
            # registrantId matcht mit personId in den Ergebnissen
            if p.get("registrantId") is not None:
                name_map[p.get("registrantId")] = p.get("name")

        # Speicherpfad festlegen
        output_txt = f"ranking_{competition_id}_{event_id}_{round_id_str}.txt"
        
        with open(output_txt, "w", encoding="utf-8") as f:
            f.write(f"WCA WCIF Live Ranking - {wcif_data.get('name')}\n")
            f.write(f"Event: {event_id} | Runde: {round_id_str}\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'Rang':<5} | {'Name':<30} | {'Single':<8} | {'Average':<8} \n")
            f.write("-" * 60 + "\n")
            
            for res in round_results:
                rank = res.get("ranking") or "-"
                person_id = res.get("personId")
                name = name_map.get(person_id, f"Teilnehmer #{person_id}")
                
                single = format_time(res.get("best"))
                average = format_time(res.get("average"))
                
                f.write(f"{rank:<5} | {name:<30} | {single:<8} | {average:<8}\n")
                
        print(f"Erfolgreich! Die WCIF-Ergebnisse fuer '{round_id_str}' wurden gespeichert unter: {output_txt}")
        
    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}")

def format_time(centiseconds):
    if not centiseconds or centiseconds <= 0:
        return "-"
    if centiseconds == -1:
        return "DNF"
    if centiseconds == -2:
        return "DNS"
    
    seconds = centiseconds / 100.0
    if seconds >= 60:
        minutes = int(seconds // 60)
        rem_seconds = seconds % 60
        return f"{minutes}:{rem_seconds:05.2f}"
    return f"{seconds:.2f}"

if __name__ == "__main__":
    # Test mit deiner Ziel-Competition
    TEST_COMP_ID = "CapelleChaosB2026" 
    TEST_EVENT_ID = "333"
    
    fetch_wca_wcif_ranking(TEST_COMP_ID, TEST_EVENT_ID)
