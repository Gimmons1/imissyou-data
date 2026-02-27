import requests
import json
import os
import sys
import urllib.parse

JSON_FILE = "library.json"
# Fonti certificate e affidabili
HEADERS = {'User-Agent': 'iMissYouApp_Core/4.1 (https://github.com/Gimmons1)'}

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
    # METODO INFALLIBILE: Usa il link esatto della pagina per trovare le date reali!
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
    except Exception as e:
        print(f"Errore date: {e}")
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

    # COMANDO 1: ELIMINA o RIFIUTA
    if issue_title.startswith("DELETE: "):
        name_to_del = issue_title.replace("DELETE: ", "").strip().lower()
        name_to_del_alt = name_to_del.replace(" ", "_")
        original_count = len(library)
        library = [p for p in library if p["name"].lower() != name_to_del and p["name"].lower() != name_to_del_alt]
        
        if len(library) < original_count:
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(library, f, indent=2, ensure_ascii=False)
            print(f"✅ Rimosso/Rifiutato: {name_to_del}")
        return

    # COMANDO 2: APPROVA UNA RICHIESTA UTENTE
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
            print(f"✅ Approvato ufficialmente: {name_to_approve}")
        return

    # COMANDO 3: AGGIUNGI (Da Admin o Da Utente)
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
        
        if not wiki_data:
            print(f"❌ Errore: '{name_to_add}' non ha una pagina Wikipedia valida.")
            sys.exit(1)

        # PULIZIA NOME: Rimuove i trattini bassi per mostrare "Alan Rickman" anziché "Alan_Rickman"
        raw_title = wiki_data.get("title", name_to_add)
        real_title = raw_title.replace("_", " ") 
        slug = wiki_data.get("titles", {}).get("canonical", raw_title)

        # EVITA DOPPIONI: Controlla anche lo slug, così blocca Queen Elizabeth se hai già Elisabetta II
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
            "approved": is_admin # TRUE se sei tu, FALSE se è un utente normale
        })
        
        library.sort(key=lambda x: x['deathDate'])
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        
        if is_admin:
            print(f"✅ Aggiunto e Pubblicato: {real_title}")
        else:
            print(f"⏳ Aggiunto (In attesa di approvazione Admin): {real_title}")

if __name__ == "__main__":
    run_processor()
