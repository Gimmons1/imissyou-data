import requests
import json
import os
import time

# File di destinazione
JSON_FILE = "library.json"

# Interroghiamo Wikidata (Fonte Ufficiale e Affidabile)
# Cerchiamo: Esseri umani, morti dopo il 1920, con almeno 40 traduzioni su Wikipedia (per garantire che siano famosissimi mondiali)
SPARQL_URL = "https://query.wikidata.org/sparql"
QUERY = """
SELECT ?person ?personLabel ?birthDate ?deathDate ?image ?sitelinks WHERE {
  ?person wdt:P31 wd:Q5. # Essere umano
  ?person wdt:P569 ?birthDate.
  ?person wdt:P570 ?deathDate.
  OPTIONAL { ?person wdt:P18 ?image. }
  
  # Filtro: Morti dal 1920 in poi
  FILTER(YEAR(?deathDate) >= 1920)
  
  # Filtro fama: devono avere una pagina Wikipedia in almeno 40 lingue
  ?person wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= 40)
  
  SERVICE wikibase:label { bd:serviceParam wikibase:language "it,en". }
}
ORDER BY DESC(?sitelinks)
LIMIT 100 # Cambia questo numero per scaricarne di più (es. 500)
"""

def get_wikipedia_bio(name, lang="it"):
    """Scarica la biografia da Wikipedia per completare i dati"""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("titles", {}).get("canonical", ""), data.get("extract", "")
    except:
        pass
    return name, "Biografia storica recuperata dagli archivi."

def run_historical_import():
    print("Contattando gli archivi ufficiali di Wikidata...")
    response = requests.get(SPARQL_URL, params={'format': 'json', 'query': QUERY})
    
    if response.status_code != 200:
        print("Errore server Wikidata.")
        return

    data = response.json()
    results = data['results']['bindings']
    print(f"Trovati {len(results)} personaggi storici illustri.")

    # Carica libreria esistente
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            library = json.load(f)
    else:
        library = []

    existing_names = [p["name"].lower() for p in library]
    new_entries = []

    for item in results:
        name = item['personLabel']['value']
        
        # Salta se è già nel database
        if name.lower() in existing_names or name.startswith("Q") or "http" in name:
            continue
            
        print(f"Elaborazione: {name}...")
        birth = item['birthDate']['value'].split('T')[0]
        death = item['deathDate']['value'].split('T')[0]
        img = item['image']['value'] if 'image' in item else None
        
        # Recupera la bio per avere uno slug valido
        slug, bio = get_wikipedia_bio(name)
        
        new_person = {
            "name": name,
            "slugs": {"IT": slug, "EN": slug},
            "bio": bio,
            "birthDate": birth,
            "deathDate": death,
            "imageUrl": img
        }
        new_entries.append(new_person)
        existing_names.append(name.lower())
        time.sleep(1) # Pausa di rispetto per i server di Wikipedia

    # Salva il file
    if new_entries:
        library.extend(new_entries)
        # Ordina per data di morte (dal più vecchio al più recente)
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"Aggiunti {len(new_entries)} nuovi personaggi storici al database!")
    else:
        print("Tutti i personaggi storici di questa ricerca sono già nel database.")

if __name__ == "__main__":
    run_historical_import()
