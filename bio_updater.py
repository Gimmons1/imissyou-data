import requests
import json
import os
import time
import urllib.parse

JSON_FILE = "library.json"

# Utilizziamo un User-Agent chiaro per rispettare le policy delle API di Wikimedia (Fonti Affidabili)
HEADERS = {
    'User-Agent': 'iMissYouApp_BioEnhancer/2.0 (https://github.com/Gimmons1)',
    'Accept': 'application/json'
}

def get_longest_wikipedia_bio(slugs):
    """
    Cerca la biografia più lunga tra le lingue disponibili (IT, EN, FR, ES)
    per evitare descrizioni vuote o troppo brevi.
    """
    best_bio = ""
    languages_to_try = ["it", "en", "fr", "es"]
    
    for lang in languages_to_try:
        lang_key = lang.upper()
        # Cerca lo slug specifico della lingua, se non c'è usa EN o IT come fallback
        slug = slugs.get(lang_key, slugs.get("EN", slugs.get("IT", "")))
        if not slug: 
            continue
        
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(slug)}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                data = res.json()
                extract = data.get("extract", "")
                
                # Evita le pagine di disambiguazione (es. quando ci sono più persone con lo stesso nome)
                if "disambiguation" not in data.get("type", "") and len(extract) > len(best_bio):
                    best_bio = extract
        except Exception as e:
            print(f"Errore recupero biografia [{lang}]: {e}")
            pass
            
    return best_bio

def get_cause_of_death(en_slug, it_slug):
    """
    Interroga Wikidata (database certificato) per scoprire la causa medica o storica del decesso.
    Usa lo slug inglese (più preciso su Wikidata) o quello italiano come riserva.
    """
    slug = en_slug if en_slug else it_slug
    if not slug: 
        return None
    
    # Query SPARQL per cercare la proprietà P509 (causa della morte)
    query = f"""
    SELECT ?causeLabel WHERE {{
      <https://en.wikipedia.org/wiki/{urllib.parse.quote(slug)}> schema:about ?item .
      ?item wdt:P509 ?cause .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "it,en". }}
    }} LIMIT 1
    """
    
    try:
        res = requests.get("https://query.wikidata.org/sparql", params={'query': query, 'format': 'json'}, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            bindings = res.json()['results']['bindings']
            if bindings:
                return bindings[0]['causeLabel']['value']
    except Exception as e:
        print(f"Errore recupero causa di morte per {slug}: {e}")
        pass
        
    return None

def run_bio_enhancer():
    print("Avvio Revisione Biografie e Ricerca Cause di Morte...")
    
    if not os.path.exists(JSON_FILE):
        print("Database non trovato.")
        return

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        try: 
            library = json.load(f)
        except Exception as e: 
            print(f"Errore lettura JSON: {e}")
            return

    updated_count = 0
    
    for person in library:
        changed = False
        current_bio = person.get("bio", "")
        
        # 1. ARRICCHIMENTO TESTO: Se la biografia è troppo corta (es. < 150 caratteri), cerca versioni migliori
        if len(current_bio) < 150:
            print(f"Biografia di {person['name']} troppo corta ({len(current_bio)} caratteri). Cerco alternative...")
            new_bio = get_longest_wikipedia_bio(person.get("slugs", {}))
            
            if new_bio and len(new_bio) > len(current_bio):
                # Se c'era già la causa di morte, la manteniamo in cima
                if "⚕️ Causa del decesso:" in current_bio:
                    causa_esistente = current_bio.split("\n\n")[0]
                    current_bio = f"{causa_esistente}\n\n{new_bio}"
                else:
                    current_bio = new_bio
                    
                person["bio"] = current_bio
                changed = True
                print(f" -> ✅ Biografia arricchita!")
        
        # 2. RICERCA CAUSA DEL DECESSO: Aggiunge la causa se non è già presente
        if "Causa del decesso:" not in current_bio:
            en_slug = person.get("slugs", {}).get("EN", "")
            it_slug = person.get("slugs", {}).get("IT", "")
            
            cause = get_cause_of_death(en_slug, it_slug)
            
            if cause:
                # Formatta la causa con la prima lettera maiuscola
                formatted_cause = cause[0].upper() + cause[1:]
                
                # Inserisce la causa di morte in cima alla biografia
                person["bio"] = f"⚕️ Causa del decesso: {formatted_cause}.\n\n{current_bio}"
                changed = True
                print(f" -> ⚕️ Trovata causa di morte per {person['name']}: {formatted_cause}")
                
        if changed:
            updated_count += 1
            
        # Breve pausa per rispettare i limiti di rate (rate-limiting) delle API
        time.sleep(0.5) 

    if updated_count > 0:
        # Ordina sempre il JSON per mantenere la timeline corretta
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Operazione conclusa! {updated_count} profili sono stati aggiornati e arricchiti.")
    else:
        print("\nTutte le schede sono già perfette. Nessun aggiornamento necessario.")

if __name__ == "__main__":
    run_bio_enhancer()
