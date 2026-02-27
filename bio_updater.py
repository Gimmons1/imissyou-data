import requests
import json
import os
import time

JSON_FILE = "library.json"
# Fonti affidabili: API ufficiali Wikipedia
HEADERS = {'User-Agent': 'iMissYouApp_BioUpdater/1.0 (https://github.com/Gimmons1)'}

def run_updater():
    print("Avvio Sincronizzazione Globale Biografie e Immagini...")
    if not os.path.exists(JSON_FILE): 
        print("Nessun database trovato.")
        return

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        try:
            library = json.load(f)
        except:
            return

    updated_count = 0
    
    for person in library:
        en_slug = person.get("slugs", {}).get("EN", "")
        it_slug = person.get("slugs", {}).get("IT", "")

        # Diamo priorità all'Italiano, altrimenti usiamo l'Inglese
        target_slug = it_slug if it_slug else en_slug
        target_lang = "it" if it_slug else "en"

        if not target_slug: continue

        url = f"https://{target_lang}.wikipedia.org/api/rest_v1/page/summary/{target_slug}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                data = res.json()
                new_bio = data.get("extract", "")
                
                changed = False
                # Aggiorna la biografia se è cambiata e non è una pagina di "errore/disambiguazione"
                if new_bio and new_bio != person.get("bio", "") and "disambiguation" not in data.get("type", ""):
                    person["bio"] = new_bio
                    changed = True
                
                # Se manca la foto, prova a recuperarla
                if not person.get("imageUrl") and "originalimage" in data:
                    person["imageUrl"] = data["originalimage"]["source"]
                    changed = True
                    
                if changed:
                    updated_count += 1
                    print(f"✅ Aggiornato profilo di: {person['name']}")
                    
        except Exception as e:
            pass
            
        time.sleep(0.5) # Pausa di sicurezza per non farci bloccare da Wikipedia

    if updated_count > 0:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        print(f"Ottimizzazione completata! {updated_count} profili aggiornati con le ultime info.")
    else:
        print("Tutti i profili sono già perfettamente aggiornati.")

if __name__ == "__main__":
    run_updater()
