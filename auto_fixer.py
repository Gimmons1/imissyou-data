import requests
import json
import os
import time

JSON_FILE = "library.json"
# Uso un User-Agent chiaro e affidabile per rispettare le policy di Wikipedia
HEADERS = {'User-Agent': 'iMissYouApp_AutoFixer/1.0 (https://github.com/Gimmons1)'}

def fetch_deep_image(person):
    en_slug = person.get("slugs", {}).get("EN", "")
    it_slug = person.get("slugs", {}).get("IT", "")

    # Livello 1 e 2: Cerca nell'API ufficiale di Wikipedia (Inglese e poi Italiano)
    for lang, slug in [("en", en_slug), ("it", it_slug)]:
        if not slug: continue
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if "originalimage" in data:
                    return data["originalimage"]["source"]
        except:
            pass

    # Livello 3: Ricerca estrema direttamente sul server centrale globale (Wikidata)
    if it_slug:
        titolo_pulito = it_slug.replace('_', ' ')
        query = f"""
        SELECT ?image WHERE {{
          ?article schema:about ?item ; schema:isPartOf <https://it.wikipedia.org/> ; schema:name "{titolo_pulito}"@it .
          ?item wdt:P18 ?image .
        }} LIMIT 1
        """
        try:
            res = requests.get("https://query.wikidata.org/sparql", params={'query': query, 'format': 'json'}, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                bindings = res.json()['results']['bindings']
                if bindings:
                    return bindings[0]['image']['value']
        except:
            pass

    return None

def run_auto_fixer():
    print("Avvio il Riparatore Automatico di Immagini...")
    if not os.path.exists(JSON_FILE):
        print("Nessun database trovato.")
        return

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        try:
            library = json.load(f)
        except:
            print("Errore nella lettura del database.")
            return

    fixed_count = 0
    for person in library:
        # Se l'immagine manca, il Riparatore entra in azione
        if not person.get("imageUrl"):
            print(f"Cerco foto ad alta affidabilità per: {person['name']}...")
            new_img = fetch_deep_image(person)
            if new_img:
                person["imageUrl"] = new_img
                fixed_count += 1
                print(f" -> ✅ Trovata e riparata: {new_img}")
            time.sleep(1) # Pausa di sicurezza per non bloccare i server

    if fixed_count > 0:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"Ottimizzazione completata. {fixed_count} immagini aggiunte o riparate automaticamente.")
    else:
        print("Tutte le immagini disponibili globalmente sono già presenti. Nessuna riparazione necessaria.")

if __name__ == "__main__":
    run_auto_fixer()
