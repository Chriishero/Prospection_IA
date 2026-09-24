import asyncio
import os
import re
import urllib.parse
import pandas as pd
from playwright.async_api import async_playwright

FICHIER = "Prospects_France_Massif.xlsx"
REGEX_EMAIL = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"


def filtrer_emails(liste_emails):
    exclus = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        "wixpress.com",
        "sentry.io",
        "google.com",
        "schema.org",
        "example.com",
        "facebook.com",
        "instagram.com",
        "bing.com",
    )
    valides = []
    for e in liste_emails:
        e_lower = e.lower()
        if not any(e_lower.endswith(ext) for ext in exclus) and not any(
            x in e_lower for x in ["example", "domain", "email@", "user"]
        ):
            valides.append(e)
    return valides


async def explorer_site_web(page, url_site):
    """Visite la page d'accueil puis la page contact du site web du prospect."""
    if not url_site or not isinstance(url_site, str) or "http" not in url_site:
        return ""

    try:
        # 1. Page d'accueil
        await page.goto(
            url_site, timeout=10000, wait_until="domcontentloaded"
        )
        await page.wait_for_timeout(1000)
        html = await page.content()
        emails = filtrer_emails(set(re.findall(REGEX_EMAIL, html)))
        if emails:
            return emails[0]

        # 2. Tentative vers la page Contact / Mentions
        liens_contact = page.locator(
            "a[href*='contact'], a[href*='mentions']"
        )
        if await liens_contact.count() > 0:
            await liens_contact.first.click(timeout=3000)
            await page.wait_for_timeout(1000)
            html_contact = await page.content()
            emails_c = filtrer_emails(set(re.findall(REGEX_EMAIL, html_contact)))
            if emails_c:
                return emails_c[0]
    except Exception:
        pass

    return ""


async def enrichir():
    if not os.path.exists(FICHIER):
        print("❌ Fichier non trouvé.")
        return

    df = pd.read_excel(FICHIER)
    total = len(df)
    modifs = 0
    premier_lancement = True

    print(
        f"🔄 Recherche Google + Exploration Sites Web sur {total} prospects...\n"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, args=["--start-maximized"]
        )
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        for idx, row in df.iterrows():
            if pd.notna(row.get("Email")) and "@" in str(row["Email"]):
                continue

            nom = str(row.get("Nom_Entreprise", ""))
            ville = str(row.get("Ville", ""))
            site_web = row.get("Site_Web")

            if not nom or nom == "nan":
                continue

            print(
                f"🔎 [{idx+1}/{total}] Recherche e-mail pour : {nom} ({ville})..."
            )
            email_trouve = ""

            try:
                # ---------------------------------------------
                # ÉTAPE 1 : RECHERCHE SUR GOOGLE
                # ---------------------------------------------
                query = f'"{nom}" "{ville}" email'
                url = (
                    f"https://www.google.fr/search?q={urllib.parse.quote(query)}"
                )

                await page.goto(url, timeout=20000)

                # Gestion CAPTCHA au démarrage
                if premier_lancement:
                    print("\n🛑 PAUSE SÉCURITÉ - VÉRIFICATION HUMAINE 🛑")
                    print("1. Valide les cookies ou le CAPTCHA si affiché.")
                    print(
                        "2. Une fois la page de recherche chargée,"
                    )
                    input(
                        "👉 Reviens dans le terminal et appuie sur ENTREE..."
                    )
                    premier_lancement = False
                    await page.wait_for_timeout(1000)

                # Vérification antirobot en cours de route
                html_google = await page.content()
                if (
                    "detected unusual traffic" in html_google
                    or "recaptcha" in html_google
                ):
                    print("\n⚠️ CAPTCHA Google détecté !")
                    input(
                        "👉 Résous le CAPTCHA dans le navigateur puis appuie sur ENTREE..."
                    )
                    await page.wait_for_timeout(1000)
                    html_google = await page.content()

                # Extraction depuis la page de résultats Google
                emails_google = filtrer_emails(
                    set(re.findall(REGEX_EMAIL, html_google))
                )
                if emails_google:
                    email_trouve = emails_google[0]
                    print(f"   ✅ E-mail trouvé sur Google : {email_trouve}")

                # ---------------------------------------------
                # ÉTAPE 2 : VISITE DU SITE WEB (SI ÉTAPE 1 INFRUCTUEUSE)
                # ---------------------------------------------
                if not email_trouve and pd.notna(site_web) and "http" in str(site_web):
                    print(f"   🌐 Exploration directe du site : {site_web}")
                    email_trouve = await explorer_site_web(page, str(site_web))
                    if email_trouve:
                        print(
                            f"   ✅ E-mail déniché sur le site web : {email_trouve}"
                        )

                # Mettre à jour si un e-mail a été extrait
                if email_trouve:
                    df.at[idx, "Email"] = email_trouve
                    modifs += 1
                    df.to_excel(FICHIER, index=False)
                    print("   💾 Fichier Excel mis à jour.")

                # Pause anti-blocage
                import random
                await page.wait_for_timeout(random.uniform(2.5, 4.5) * 1000)

            except Exception as e:
                print(f"   ⚠️ Erreur : {e}")
                continue

        await browser.close()

    print(
        f"\n🎉 ENRICHISSEMENT TERMINÉ ! {modifs} nouveaux e-mails récupérés."
    )


if __name__ == "__main__":
    asyncio.run(enrichir())