import requests
import json
import os
import sys

JSON_FILE = "library.json"
HEADERS = {'User-Agent': 'iMissYouApp_AdminCore/2.0 (https://github.com/Gimmons1)'}

def fetch_wikipedia_data(name, lang="it"):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            # Verifica che sia un profilo reale e non una pagina vuota
            if "extract" in data and len(data["extract"]) > 50:
                return data
    except: pass
    return None

def run_processor():
    issue_title = os.environ.get("ISSUE_TITLE", "")
    if not issue_title: return

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        library = json.load(f)

    # CASO 1: ELIMINAZIONE
    if issue_title.startswith("DELETE: "):
        name_to_del = issue_title.replace("DELETE: ", "").strip().lower()
        original_count = len(library)
        library = [p for p in library if p["name"].lower() != name_to_del]
        if len(library) < original_count:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
            print(f"✅ Eliminato: {name_to_del}")
        return

    # CASO 2: AGGIUNTA
    if issue_title.startswith("REQUEST: "):
        name_to_add = issue_title.replace("REQUEST: ", "").strip()
        
        # Pre-verifica: Se Wikipedia non risponde bene, interrompi tutto
        wiki_data = fetch_wikipedia_data(name_to_add, "it") or fetch_wikipedia_data(name_to_add, "en")
        
        if not wiki_data:
            print(f"❌ Errore: '{name_to_add}' non ha una pagina Wikipedia valida. Operazione annullata.")
            sys.exit(1) # Forza l'errore per non fare il commit

        real_title = wiki_data.get("titles", {}).get("canonical", name_to_add)
        
        # Evita duplicati
        if any(p["name"].lower() == real_title.lower() for p in library):
            print("Già in archivio.")
            return

        # Recupera date da Wikidata (Omesso per brevità, usa la funzione dei file precedenti)
        # Qui aggiungi il personaggio
        library.append({
            "name": real_title,
            "slugs": {"IT": real_title, "EN": real_title},
            "bio": wiki_data.get("extract", ""),
            "birthDate": "1900-01-01", # Da automatizzare con wikidata
            "deathDate": "2024-01-01",
            "imageUrl": wiki_data.get("originalimage", {}).get("source", None),
            "approved": True
        })
        
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"✅ Aggiunto: {real_title}")

if __name__ == "__main__":
    run_processor()
