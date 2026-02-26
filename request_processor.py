import requests
import json
import os
import sys

JSON_FILE = "library.json"
HEADERS = {'User-Agent': 'iMissYouApp_RequestProcessor/1.0 (https://github.com/Gimmons1)'}

def fetch_wikipedia_data(name, lang="it"):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def fetch_wikidata_dates(title, lang="it"):
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
                d = bindings[0].get('deathDate', {}).get('value', '2000-01-01').split('T')[0]
                return b, d
    except:
        pass
    return "1900-01-01", "2000-01-01"

def process_request(requested_name):
    print(f"Elaborazione richiesta per: {requested_name}")
    
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: library = []
    else:
        library = []

    existing_names = [p["name"].lower().strip() for p in library]
    
    if requested_name.lower() in existing_names:
        print("Il personaggio è già presente in archivio.")
        sys.exit(0) # Esce senza fare nulla

    wiki_data = fetch_wikipedia_data(requested_name)
    
    if wiki_data:
        real_title = wiki_data.get("titles", {}).get("canonical", requested_name)
        bio = wiki_data.get("extract", "Biografia in aggiornamento.")
        img = wiki_data.get("originalimage", {}).get("source", None)
        birth, death = fetch_wikidata_dates(real_title)
        
        library.append({
            "name": real_title,
            "slugs": {"IT": real_title, "EN": real_title},
            "bio": bio,
            "birthDate": birth,
            "deathDate": death,
            "imageUrl": img,
            "approved": True
        })
        
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"✅ Successo: {real_title} aggiunto al database!")
    else:
        print(f"❌ Impossibile trovare '{requested_name}' su Wikipedia. Controllare l'ortografia.")

if __name__ == "__main__":
    # Prende il nome richiesto dalle variabili di ambiente di GitHub Actions
    issue_title = os.environ.get("ISSUE_TITLE", "")
    if issue_title.startswith("REQUEST: "):
        name = issue_title.replace("REQUEST: ", "").strip()
        process_request(name)
    else:
        print("Nessuna richiesta valida trovata.")
