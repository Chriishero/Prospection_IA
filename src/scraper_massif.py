import asyncio
import os
import re
import urllib.parse
from bs4 import BeautifulSoup
import pandas as pd
from playwright.async_api import async_playwright
import requests

# ==========================================
# 1. SECTEURS À FORTE CONSOMMATION D'ÉNERGIE
# ==========================================
METIERS = [
    "Boulangerie Patisserie",
    "Boucherie Charcuterie",
    "Poissonnerie",
    "Chambre froide / Entrepôt frigorifique",
    "Supermarché / Hypermarché",
    "Restaurant / Brasserie",
    "Pizzéria",
    "Traiteur / Cuisine centrale",
    "Hôtel Spa",
    "Camping",
    "Salle de sport",
    "Pressing / Blanchisserie",
    "Laverie automatique",
    "Station de lavage automobile",
    "Scierie",
    "Imprimerie",
    "Metallerie / Chaudronnerie",
    "Carrosserie",
    "Garage automobile",
    "Usine / Agroalimentaire",
    "Clinique privée",
    "Laboratoire d'analyses médicales",
    "EHPAD",
    "Jardinerie",
]

# ==========================================
# 2. TOP VILLES ET METROPOLES DE FRANCE
# ==========================================
VILLES = [
    "Paris",
    "Marseille",
    "Lyon",
    "Toulouse",
    "Nice",
    "Nantes",
    "Montpellier",
    "Strasbourg",
    "Bordeaux",
    "Lille",
    "Rennes",
    "Reims",
    "Toulon",
    "Saint-Étienne",
    "Le Havre",
    "Grenoble",
    "Dijon",
    "Angers",
    "Nîmes",
    "Aix-en-Provence",
    "Clermont-Ferrand",
    "Le Mans",
    "Brest",
    "Tours",
    "Amiens",
    "Limoges",
    "Annecy",
    "Perpignan",
    "Metz",
    "Besançon",
    "Orléans",
    "Rouen",
    "Mulhouse",
    "Caen",
    "Nancy",
    "Avignon",
    "Dunkerque",
    "Poitiers",
    "Versailles",
    "Pau",
    "Béziers",
    "Calais",
    "La Rochelle",
    "Saint-Nazaire",
    "Colmar",
    "Ajaccio",
    "Bourges",
    "Quimper",
    "Valence",
    "Niort",
    "Lorient",
    "Chambéry",
    "Montauban",
    "Troyes",
    "Brive-la-Gaillarde",
    "Tarbes",
]

FICHIER_RESULTATS = "Prospects_France_Massif.xlsx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# ==========================================
# 3. EXTRACTION D'EMAIL DEPUIS UN SITE WEB
# ==========================================
def extraire_email_du_site(url_site):
    if not url_site or not isinstance(url_site, str) or "http" not in url_site:
        return ""

    try:
        url_base = (
            url_site if url_site.startswith("http") else f"http://{url_site}"
        )
        res = requests.get(url_base, headers=HEADERS, timeout=5)
        if res.status_code != 200:
            return ""

        # Recherche dans la page d'accueil
        emails = set(
            re.findall(
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", res.text
            )
        )
        emails_valides = [
            e
            for e in emails
            if not e.lower().endswith(
                (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".svg",
                    ".webp",
                    "wixpress.com",
                    "sentry.io",
                )
            )
        ]

        if emails_valides:
            return emails_valides[0]

        # Recherche dans les sous-pages (Contact / Mentions)
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if "contact" in href or "mentions" in href:
                lien_contact = urllib.parse.urljoin(url_base, a["href"])
                try:
                    res_c = requests.get(
                        lien_contact, headers=HEADERS, timeout=4
                    )
                    emails_c = set(
                        re.findall(
                            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                            res_c.text,
                        )
                    )
                    emails_c_valides = [
                        e
                        for e in emails_c
                        if not e.lower().endswith(
                            (".png", ".jpg", ".jpeg", ".gif", ".svg")
                        )
                    ]
                    if emails_c_valides:
                        return emails_c_valides[0]
                except Exception:
                    pass
    except Exception:
        pass

    return ""


# ==========================================
# 4. MOTEUR DE SCRAPING MASSIF
# ==========================================
async def scraper_tout():
    prospects_existants = set()

    # Charger le fichier s'il existe déjà pour reprendre l'extraction sans doublons
    if os.path.exists(FICHIER_RESULTATS):
        try:
            df_ex = pd.read_excel(FICHIER_RESULTATS)
            if "Nom_Entreprise" in df_ex.columns:
                prospects_existants = set(
                    df_ex["Nom_Entreprise"].dropna().tolist()
                )
            prospects_liste = df_ex.to_dict("records")
        except Exception:
            prospects_liste = []
    else:
        prospects_liste = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False
        )  # En garde en visuel pour contrôle
        context = await browser.new_context()
        page = await context.new_page()

        total_combinaisons = len(METIERS) * len(VILLES)
        compteur = 0

        for metier in METIERS:
            for ville in VILLES:
                compteur += 1
                recherche = f"{metier} {ville}"
                print(
                    f"\n🚀 [{compteur}/{total_combinaisons}] Recherche : {recherche}"
                )

                try:
                    url = f"https://www.google.com/maps/search/{recherche.replace(' ', '+')}"
                    await page.goto(url, timeout=30000)
                    await page.wait_for_timeout(2000)

                    # Gestion du bandeau cookies
                    try:
                        btn_cookie = page.locator(
                            "button[aria-label*='Tout refuser'], button[aria-label*='Reject all']"
                        )
                        if await btn_cookie.count() > 0:
                            await btn_cookie.first.click(timeout=2000)
                    except Exception:
                        pass

                    # Defilement dans le panneau de gauche
                    try:
                        feed = page.locator("div[role='feed']")
                        if await feed.count() > 0:
                            for _ in range(3):
                                await feed.evaluate(
                                    "node => node.scrollTop += 2000"
                                )
                                await page.wait_for_timeout(1000)
                    except Exception:
                        pass

                    # Recuperation des fiches
                    items = await page.locator("a[href*='/maps/place/']").all()
                    if not items:
                        items = await page.locator("div[role='article']").all()

                    print(f"   └─ {len(items)} fiches détectées.")

                    nouveaux_ajoutes = 0

                    for item in items[:10]:
                        try:
                            # Titre / Nom
                            nom = await item.get_attribute("aria-label")
                            if not nom:
                                text_el = await item.inner_text()
                                nom = (
                                    text_el.split("\n")[0] if text_el else ""
                                )

                            if not nom or nom in prospects_existants:
                                continue

                            await item.click()
                            await page.wait_for_timeout(1500)

                            adresse, site_web, tel = "", "", ""

                            # Recherche adresse
                            adr_locator = page.locator(
                                "button[data-item-id*='address'], [data-tooltip*='adresse']"
                            )
                            if await adr_locator.count() > 0:
                                adresse = await adr_locator.first.inner_text()

                            # Recherche site web
                            web_locator = page.locator(
                                "a[data-item-id*='authority'], a[aria-label*='site web']"
                            )
                            if await web_locator.count() > 0:
                                site_web = await web_locator.first.get_attribute(
                                    "href"
                                )

                            # Recherche téléphone
                            tel_locator = page.locator(
                                "button[data-item-id*='phone'], [data-tooltip*='téléphone']"
                            )
                            if await tel_locator.count() > 0:
                                tel = await tel_locator.first.inner_text()

                            # Extraction e-mail
                            email = ""
                            if site_web:
                                email = extraire_email_du_site(site_web)

                            nouveau_prospect = {
                                "Nom_Dirigeant": "",
                                "Nom_Entreprise": nom,
                                "Email": email,
                                "Adresse": adresse,
                                "Ville": ville,
                                "Secteur": metier,
                                "Telephone": tel,
                                "Site_Web": site_web,
                            }

                            prospects_liste.append(nouveau_prospect)
                            prospects_existants.add(nom)
                            nouveaux_ajoutes += 1

                            print(
                                f"      ➕ Prospect : {nom} | Mail: {email if email else 'Non trouvé'}"
                            )

                        except Exception:
                            continue

                    # Sauvegarde dans Excel après chaque ville
                    if nouveaux_ajoutes > 0:
                        df_temp = pd.DataFrame(prospects_liste)
                        df_temp.to_excel(FICHIER_RESULTATS, index=False)
                        print(
                            f"   💾 Fichier Excel mis à jour ({len(prospects_liste)} prospects au total)."
                        )

                except Exception as e:
                    print(f"⚠️ Erreur sur {recherche} : {e}")
                    continue

        await browser.close()

    print(
        f"\n🎉 SCRAPING TERMINÉ ! Total : {len(prospects_liste)} prospects enregistrés dans '{FICHIER_RESULTATS}'."
    )


if __name__ == "__main__":
    asyncio.run(scraper_tout())