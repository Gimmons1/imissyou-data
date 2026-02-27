import requests
import json
import os
import sys

JSON_FILE = "library.json"
HEADERS = {'User-Agent': 'iMissYouApp_AdminCore/2.0 (https://github.com/Gimmons1)'}

def fetch_wikipedia_data(name, lang="it"):
    # Cerca il nome esatto su Wikipedia (Fonte Affidabile)
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            # CONTROLLO ANTI-CARTELLE VUOTE: 
            # Verifica che sia un profilo reale, non una pagina di "disambiguazione" e che la bio esista.
            if "extract" in data and len(data["extract"]) > 30 and data.get("type") != "disambiguation":
                return data
    except: 
        pass
    return None

def fetch_wikidata_dates(title, lang="it"):
    # Cerca le date di nascita e morte su Wikidata (Fonte Affidabile)
    query = f"""
    SELECT ?birthDate ?deathDate WHERE {{
      ?article schema:about ?item ; schema:isPartOf <https://{lang}.wikipedia.org/> ; schema:name "{title}"@str .
      OPTIONAL {{ ?item wdt:P569 ?birthDate . }}
      OPTIONAL {{ ?item wdt:P570 ?deathDate . }}
    }} LIMIT 1
    """
    try:
        res = requests.get("https://query.wikidata.org/sparql", params={'query': query, 'format': 'json'}, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            bindings = res.json()['results']['bindings']
            if bindings:
                b = bindings[0].get('birthDate', {}).get('value', '1900-01-01').split('T')[0]
                d = bindings[0].get('deathDate', {}).get('value', '2024-01-01').split('T')[0]
                return b, d
    except:
        pass
    return "1900-01-01", "2024-01-01"

def run_processor():
    # Prende il comando inviato dall'app
    issue_title = os.environ.get("ISSUE_TITLE", "")
    if not issue_title: 
        return

    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: library = []
    else:
        library = []

    # COMANDO 1: ELIMINA TESSERA
    if issue_title.startswith("DELETE: "):
        name_to_del = issue_title.replace("DELETE: ", "").strip().lower()
        original_count = len(library)
        library = [p for p in library if p["name"].lower() != name_to_del]
        
        if len(library) < original_count:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
            print(f"✅ Rimosso definitivamente: {name_to_del}")
        else:
            print("Personaggio non trovato nel database.")
        return

    # COMANDO 2: AGGIUNGI TESSERA
    if issue_title.startswith("REQUEST: "):
        name_to_add = issue_title.replace("REQUEST: ", "").strip()
        
        # Pre-verifica: Cerca prima in Italiano, poi in Inglese
        wiki_data = fetch_wikipedia_data(name_to_add, "it") or fetch_wikipedia_data(name_to_add, "en")
        
        if not wiki_data:
            print(f"❌ Errore: '{name_to_add}' non ha una pagina Wikipedia valida. Scarto per evitare schede vuote.")
            sys.exit(1) # Esce con errore per non salvare modifiche inutili

        real_title = wiki_data.get("titles", {}).get("canonical", name_to_add)
        
        if any(p["name"].lower() == real_title.lower() for p in library):
            print("Già in archivio.")
            return

        birth, death = fetch_wikidata_dates(real_title)
        
        library.append({
            "name": real_title,
            "slugs": {"IT": real_title, "EN": real_title},
            "bio": wiki_data.get("extract", "Biografia non disponibile."),
            "birthDate": birth,
            "deathDate": death,
            "imageUrl": wiki_data.get("originalimage", {}).get("source", None),
            "approved": True
        })
        
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"✅ Aggiunto con successo: {real_title}")

if __name__ == "__main__":
    run_processor()
