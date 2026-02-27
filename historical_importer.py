import requests
import json
import os
import time
from datetime import datetime
import urllib.parse

JSON_FILE = "library.json"
SPARQL_URL = "https://query.wikidata.org/sparql"
# Fonti certificate e affidabili
HEADERS = {
    'User-Agent': 'iMissYouApp_Historical/9.1 (https://github.com/Gimmons1)',
    'Accept': 'application/sparql-results+json'
}

# Il calendario dinamico calcola l'anno in automatico (2026, 2027, ecc.)
ANNO_CORRENTE = datetime.now().year

EPOCHE = [
    (1980, 1989),
    (1990, 1999),
    (2000, 2009),
    (2010, 2019),
    (2020, ANNO_CORRENTE) # <- Si aggiorna da solo fino ad oggi!
]

def get_wikipedia_bio(slug, lang="it"):
    # Usa l'URL esatto per evitare errori con spazi e caratteri strani
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(slug)}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=(5, 5))
        if response.status_code == 200:
            data = response.json()
            return data.get("titles", {}).get("canonical", slug), data.get("extract", "")
    except:
        pass
    return slug.replace('_', ' '), "Biografia recuperata dagli archivi ufficiali."

def run_historical_import():
    print(f"Avvio ricerca dinamica (fino al {ANNO_CORRENTE})...")
    
    library = []
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: pass

    # FILTRO ANTI-DOPPIONI: Usa lo SLUG (ID univoco) e ignora il nome testuale
    existing_slugs = set()
    for p in library:
        for val in p.get("slugs", {}).values():
            existing_slugs.add(val.lower())

    new_entries = []

    for inizio, fine in EPOCHE:
        print(f"\n--- Ricerca VIP: {inizio} - {fine} ---")
        
        query = f"""
        SELECT ?person ?personLabel ?birthDate ?deathDate ?image ?sitelinks ?article WHERE {{
          ?person wdt:P31 wd:Q5. 
          ?person wdt:P570 ?deathDate.
          FILTER(YEAR(?deathDate) >= {inizio} && YEAR(?deathDate) <= {fine})
          ?person wikibase:sitelinks ?sitelinks .
          FILTER(?sitelinks >= 40)
          ?person wdt:P569 ?birthDate.
          OPTIONAL {{ ?person wdt:P18 ?image. }}
          OPTIONAL {{
            ?article schema:about ?person .
            ?article schema:isPartOf <https://en.wikipedia.org/> .
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "it,en". }}
        }}
        ORDER BY DESC(?sitelinks)
        LIMIT 100
        """
        
        for attempt in range(3):
            try:
                response = requests.get(SPARQL_URL, params={'query': query}, headers=HEADERS, timeout=(10, 30))
                if response.status_code == 200:
                    results = response.json()['results']['bindings']
                    print(f" -> Trovate {len(results)} figure di spicco.")
                    
                    for item in results:
                        raw_name = item['personLabel']['value'].strip()
                        # Se il nome inizia con Q è un errore temporaneo del database, lo saltiamo
                        if raw_name.startswith("Q") and raw_name[1:].isdigit(): 
                            continue
                            
                        # Estrae lo slug inglese pulito dall'URL per identificare la persona
                        article_url = item.get('article', {}).get('value', '')
                        slug_en = article_url.split('/')[-1] if article_url else raw_name.replace(' ', '_')
                        slug_en = urllib.parse.unquote(slug_en)
                        
                        if slug_en.lower() in existing_slugs:
                            continue
                            
                        birth = item['birthDate']['value'].split('T')[0]
                        death = item['deathDate']['value'].split('T')[0]
                        img = item['image']['value'] if 'image' in item else None
                        
                        # RIMUOVE GLI UNDERSCORE: Il nome mostrato nell'App sarà perfetto
                        clean_name = raw_name.replace('_', ' ')
                        it_slug, bio = get_wikipedia_bio(slug_en)
                        
                        new_entries.append({
                            "name": clean_name, 
                            "slugs": {"IT": it_slug.replace(' ', '_'), "EN": slug_en},
                            "bio": bio, 
                            "birthDate": birth, 
                            "deathDate": death, 
                            "imageUrl": img, 
                            "approved": True
                        })
                        existing_slugs.add(slug_en.lower())
                        existing_slugs.add(it_slug.lower().replace(' ', '_'))
                        time.sleep(0.2)
                    break
                else:
                    time.sleep(5)
            except Exception as e:
                time.sleep(5)

    if new_entries:
        library.extend(new_entries)
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"\n✅ SUCCESSO: {len(new_entries)} VIP aggiunti alla biblioteca!")
    else:
        print("\nNessun nuovo VIP trovato (o tutti i VIP scansionati sono già presenti).")

if __name__ == "__main__":
    run_historical_import()
