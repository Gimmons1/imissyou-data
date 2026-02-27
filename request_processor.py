import requests
import json
import os
import sys
import urllib.parse

JSON_FILE = "library.json"
HEADERS = {'User-Agent': 'iMissYouApp_Core/5.5 (https://github.com/Gimmons1)'}

# NUOVA FUNZIONE: Tenta di auto-correggere gli errori di battitura (es. Emmywinhouse -> Amy Winehouse)
def suggest_correct_name(query, lang="it"):
    url = f"https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit=1&format=json"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if len(data) > 1 and len(data[1]) > 0:
                return data[1][0] # Restituisce il nome corretto suggerito
    except: pass
    return None

def fetch_wikipedia_data(name, lang="it"):
    slug = name.replace(' ', '_')
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(slug)}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if "extract" in data and len(data["extract"]) > 30 and data.get("type") != "disambiguation":
                return data
    except: pass
    return None

def fetch_wikidata_dates(slug, lang="it"):
    wiki_url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(slug)}"
    query = f"""
    SELECT ?birthDate ?deathDate WHERE {{
      <{wiki_url}> schema:about ?item .
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
    except: pass
    return "1900-01-01", "2024-01-01"

def run_processor():
    issue_title = os.environ.get("ISSUE_TITLE", "")
    if not issue_title: return

    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try: library = json.load(f)
            except: library = []
    else:
        library = []

    # COMANDO: ELIMINA o RIFIUTA
    if issue_title.startswith("DELETE: "):
        name_to_del = issue_title.replace("DELETE: ", "").strip().lower()
        name_to_del_alt = name_to_del.replace(" ", "_")
        original_count = len(library)
        library = [p for p in library if p["name"].lower() != name_to_del and p["name"].lower() != name_to_del_alt]
        
        if len(library) < original_count:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
        return

    # COMANDO: APPROVA UNA RICHIESTA UTENTE
    if issue_title.startswith("APPROVE: "):
        name_to_approve = issue_title.replace("APPROVE: ", "").strip().lower()
        found = False
        for p in library:
            if p["name"].lower() == name_to_approve or p["name"].lower() == name_to_approve.replace(" ", "_"):
                p["approved"] = True
                found = True
                break
        if found:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
        return

    # COMANDO: AGGIUNGI (Admin o Utente)
    is_admin = issue_title.startswith("ADMIN_REQUEST: ")
    is_user = issue_title.startswith("USER_REQUEST: ")

    if is_admin or is_user:
        prefix = "ADMIN_REQUEST: " if is_admin else "USER_REQUEST: "
        name_to_add = issue_title.replace(prefix, "").strip()
        
        wiki_data = fetch_wikipedia_data(name_to_add, "it")
        lang_used = "it"
        if not wiki_data:
            wiki_data = fetch_wikipedia_data(name_to_add, "en")
            lang_used = "en"
            
        # SE FALLISCE -> PROVA L'AUTOCORREZIONE (Emmywinhouse -> Amy Winehouse)
        if not wiki_data:
            print(f"Nome esatto non trovato. Tento autocorrezione per '{name_to_add}'...")
            suggested = suggest_correct_name(name_to_add, "it") or suggest_correct_name(name_to_add, "en")
            if suggested:
                print(f"Forse intendevi: {suggested}")
                wiki_data = fetch_wikipedia_data(suggested, "it")
                lang_used = "it"
                if not wiki_data:
                    wiki_data = fetch_wikipedia_data(suggested, "en")
                    lang_used = "en"

        # SE FALLISCE ANCORA -> CREA SCHEDA DI ERRORE PER L'ADMIN
        if not wiki_data:
            print(f"❌ Errore totale: '{name_to_add}' non trovato. Creo scheda di errore in attesa.")
            library.append({
                "name": f"⚠️ ERRORE: {name_to_add}",
                "slugs": {"IT": "", "EN": ""},
                "bio": "ATTENZIONE ADMIN: Il server non ha trovato nessuna pagina Wikipedia per questo nome (nemmeno provando a correggerlo). Usa il cestino rosso per eliminare questa scheda e prova a rifare la richiesta usando il Nome e Cognome esatti.",
                "birthDate": "1900-01-01",
                "deathDate": "2024-01-01",
                "imageUrl": None,
                "approved": False # Rimane "In attesa" così la vedi e la cestini!
            })
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
            sys.exit(0)

        # SE È TUTTO OK -> SALVA NORMALMENTE
        raw_title = wiki_data.get("title", name_to_add)
        real_title = raw_title.replace("_", " ") 
        slug = wiki_data.get("titles", {}).get("canonical", raw_title)

        for p in library:
            if p["name"].lower() == real_title.lower() or p["slugs"].get("EN", "").lower() == slug.lower() or p["slugs"].get("IT", "").lower() == slug.lower():
                print("Già in archivio.")
                return

        birth, death = fetch_wikidata_dates(slug, lang_used)
        
        library.append({
            "name": real_title,
            "slugs": {"IT": slug, "EN": slug},
            "bio": wiki_data.get("extract", "Biografia non disponibile."),
            "birthDate": birth,
            "deathDate": death,
            "imageUrl": wiki_data.get("originalimage", {}).get("source", None),
            "approved": is_admin
        })
        
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"✅ Salvato: {real_title}")

if __name__ == "__main__":
    run_processor()
