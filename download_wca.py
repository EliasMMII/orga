import json
import requests

def download_competition_data(competition_id):
    print(f"Lade WCIF-Daten fuer '{competition_id}' direkt herunter...")
    
    # KORREKTUR: Der tatsaechliche API-Pfad fuer den direkten JSON-Download
    wcif_url = f"https://www.worldcubeassociation.org/api/v0/competitions/{competition_id}/wcif/public"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(wcif_url, headers=headers)
        response.raise_for_status()
        
        # Speichere die Datei direkt im Projektordner ab
        with open("competition_data.json", "w", encoding="utf-8") as f:
            json.dump(response.json(), f, indent=4, ensure_ascii=False)
            
        print("Erfolgreich! 'competition_data.json' wurde automatisch gespeichert.")
        
    except Exception as e:
        print(f"Fehler beim automatischen Download: {e}")

if __name__ == "__main__":
    COMP_ID = "RubiksGermanNationals2026"
    download_competition_data(COMP_ID)
