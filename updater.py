import requests
import json
import os
import time
import urllib.parse
from datetime import datetime, timedelta

JSON_FILE = "library.json"
SPARQL_URL = "https://query.wikidata.org/sparql"
# Fonti certificate e affidabili (Wikidata)
HEADERS = {
    'User-Agent': 'iMissYouApp_RecentSentinel/7.0 (https://github.com/Gimmons1)',
    'Accept': 'application/sparql-results+json'
}

def get_wikipedia_bio(slug, lang="it"):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(slug)}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=(5, 5))
        if response.status_code == 200:
            data = response.json()
            return data.get("titles", {}).get("canonical", slug), data.get("extract", "")
    except:
        pass
    return slug.replace('_', ' '), "Biografia in attesa di aggiornamento."

def run_updater():
    # Cerca nell'ultimo anno solare
    data_limite = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00Z")
    print(f"--- Sentinel Attiva: Cerco decessi dal {data_limite[:10]} ad oggi ---")
    
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: library = []
    else:
        library = []

    existing_slugs = set()
    for p in library:
        for val in p.get("slugs", {}).values():
            existing_slugs.add(val.lower())

    new_entries = []

    query = f"""
    SELECT ?person ?personLabel ?birthDate ?deathDate ?image ?sitelinks ?article WHERE {{
      ?person wdt:P31 wd:Q5. 
      ?person wdt:P570 ?deathDate.
      FILTER(?deathDate >= "{data_limite}"^^xsd:dateTime)
      ?person wikibase:sitelinks ?sitelinks .
      FILTER(?sitelinks >= 25)
      OPTIONAL {{ ?person wdt:P569 ?birthDate. }}
      OPTIONAL {{ ?person wdt:P18 ?image. }}
      OPTIONAL {{
        ?article schema:about ?person .
        ?article schema:isPartOf <https://en.wikipedia.org/> .
      }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "it,en". }}
    }}
    ORDER BY DESC(?deathDate)
    LIMIT 50
    """
    
    try:
        response = requests.get(SPARQL_URL, params={'query': query}, headers=HEADERS, timeout=(10, 30))
        if response.status_code == 200:
            results = response.json()['results']['bindings']
            print(f" -> Trovate {len(results)} figure di spicco recenti.")
            
            for item in results:
                raw_name = item['personLabel']['value'].strip()
                if raw_name.startswith("Q") and raw_name[1:].isdigit(): 
                    continue
                    
                article_url = item.get('article', {}).get('value', '')
                slug_en = article_url.split('/')[-1] if article_url else raw_name.replace(' ', '_')
                slug_en = urllib.parse.unquote(slug_en)
                
                if slug_en.lower() in existing_slugs:
                    continue
                    
                birth = item.get('birthDate', {}).get('value', '1900-01-01T').split('T')[0]
                death = item.get('deathDate', {}).get('value', '2024-01-01T').split('T')[0]
                img = item.get('image', {}).get('value', None)
                
                clean_name = raw_name.replace('_', ' ')
                it_slug, bio = get_wikipedia_bio(slug_en)
                
                new_entries.append({
                    "name": clean_name, 
                    "slugs": {"IT": it_slug.replace(' ', '_'), "EN": slug_en},
                    "bio": bio, # ✅ Il testo tecnico è stato rimosso. Biografia perfettamente pulita.
                    "birthDate": birth, 
                    "deathDate": death, 
                    "imageUrl": img, 
                    "approved": False 
                })
                existing_slugs.add(slug_en.lower())
                existing_slugs.add(it_slug.lower().replace(' ', '_'))
                time.sleep(0.2)
    except Exception as e:
        print(f"Errore durante la ricerca: {e}")

    if new_entries:
        library.extend(new_entries)
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"--- Salvati {len(new_entries)} nuovi decessi da approvare! ---")
    else:
        print("--- Nessuna nuova aggiunta necessaria. ---")

if __name__ == "__main__":
    run_updater()
