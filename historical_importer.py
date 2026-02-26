import requests
import json
import os
import time

JSON_FILE = "library.json"
SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = {'User-Agent': 'iMissYouApp_DeepSearch/3.0 (https://github.com/Gimmons1)'}

# RICERCA PROFONDA: Ora cerca 2000 persone! 
# Filtro fama abbassato a 25 lingue (perfetto per intercettare icone come Carrà o Rickman)
QUERY = """
SELECT ?person ?personLabel ?birthDate ?deathDate ?image ?sitelinks WHERE {
  ?person wdt:P31 wd:Q5. 
  ?person wdt:P569 ?birthDate.
  ?person wdt:P570 ?deathDate.
  OPTIONAL { ?person wdt:P18 ?image. }
  FILTER(YEAR(?deathDate) >= 1920)
  ?person wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= 25)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "it,en". }
}
ORDER BY DESC(?sitelinks)
LIMIT 2000
"""

def get_wikipedia_bio(name, lang="it"):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("titles", {}).get("canonical", ""), data.get("extract", "")
    except Exception:
        pass
    return name, "Biografia storica recuperata dagli archivi ufficiali."

def run_historical_import():
    print("Avvio ricerca profonda su Wikidata (Fino a 2000 celebrità)...")
    response = requests.get(SPARQL_URL, params={'format': 'json', 'query': QUERY}, headers=HEADERS)
    if response.status_code != 200: raise Exception("Errore Wikidata")

    results = response.json()['results']['bindings']
    library = []
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: pass

    existing_names = set(p["name"].lower().strip() for p in library)
    new_entries = []

    for item in results:
        name = item['personLabel']['value'].strip()
        name_lower = name.lower()
        
        if name_lower in existing_names or name.startswith("Q") or "http" in name: 
            continue
            
        print(f"Scaricando: {name}...")
        birth = item['birthDate']['value'].split('T')[0]
        death = item['deathDate']['value'].split('T')[0]
        img = item['image']['value'] if 'image' in item else None
        slug, bio = get_wikipedia_bio(name)
        
        new_entries.append({
            "name": name, 
            "slugs": {"IT": slug, "EN": slug},
            "bio": bio, 
            "birthDate": birth, 
            "deathDate": death, 
            "imageUrl": img,
            "approved": True # I dati storici di Wikipedia sono sempre pre-approvati
        })
        existing_names.add(name_lower)
        time.sleep(0.5)

    if new_entries:
        library.extend(new_entries)
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"✅ SUCCESSO: Aggiunti {len(new_entries)} personaggi.")

if __name__ == "__main__":
    run_historical_import()
