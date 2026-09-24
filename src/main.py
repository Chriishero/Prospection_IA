import glob
import os
import random
import smtplib
import subprocess
import sys
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ollama
import pandas as pd

from traiter_reponses_imap import relever_boite_et_appliquer_optout
from config import EXPEDITEURS, SMTP_SERVER, SMTP_PORT

# ==========================================
# 1. CONFIGURATION & QUOTAS
# ==========================================
MAX_MAILS_PAR_COMPTE = 125

DELAI_RELANCE_1 = 4  # 4 jours après Mail 1
DELAI_RELANCE_2 = 5  # 5 jours après Relance 1
DELAI_RELANCE_3 = 5  # 5 jours après Relance 2

URL_CALENDLY = "https://calendly.com/a-mirabel-stratenergies/analyse-de-vos-besoins-energetiques-audit-gratuit"
LIEN_HTML_CLIQUABLE = (
    f'<a href="{URL_CALENDLY}">👉 Pour réserver un créneau c\'est juste ici</a>'
)
ADRESSE_SIGNATURE = "50 chemin des pradels, Fuveau, 13710"

PLAGE_ENVOIE = (1, 23)

STATUTS_EXCLUS = [
    "Désinscrit",
    "Stop",
    "RDV Pris",
    "A Répondu",
    "Relance 3 Envoyée",
    "Intéressé - Calendly Envoyé",
    "Intéressé - À Relancer Manuellement",
]


# ==========================================
# 2. VÉRIFICATION ET DÉMARRAGE OLLAMA
# ==========================================
def verifier_et_demarrer_ollama():
    try:
        ollama.list()
        print("⚡ Serveur Ollama actif.")
    except Exception:
        print("🔄 Démarrage automatique d'Ollama en arrière-plan...")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        time.sleep(3)


# ==========================================
# 3. CHARGEMENT AUTOMATIQUE DU FICHIER
# ==========================================
def charger_fichier_prospects(chemin_fichier=None):
    if chemin_fichier:
        fichier_cible = chemin_fichier
    else:
        fichiers = glob.glob("*.xlsx") + glob.glob("*.csv") + glob.glob("*.xls")
        fichiers = [f for f in fichiers if not f.startswith("~$")]

        if not fichiers:
            raise FileNotFoundError(
                "❌ Aucun fichier Excel (.xlsx, .xls) ou CSV (.csv) trouvé !"
            )

        fichier_cible = fichiers[0]
    print(f"📁 Fichier chargé : {fichier_cible}")

    if fichier_cible.endswith(".csv"):
        try:
            df = pd.read_csv(fichier_cible, sep=";")
        except Exception:
            df = pd.read_csv(fichier_cible, sep=",")
    else:
        df = pd.read_excel(fichier_cible)

    return df, fichier_cible


def mapper_colonnes_automatiquement(df):
    mapping = {
        "email": None,
        "nom_dirigeant": None,
        "nom_entreprise": None,
        "adresse": None,
        "ville": None,
    }

    for col in df.columns:
        col_clean = str(col).lower().strip()

        if not mapping["email"] and ("email" in col_clean or "mail" in col_clean):
            mapping["email"] = col
        elif not mapping["nom_dirigeant"] and (
            "dirigeant" in col_clean
            or "contact" in col_clean
            or "prenom" in col_clean
            or "nom" in col_clean
        ):
            mapping["nom_dirigeant"] = col
        elif not mapping["nom_entreprise"] and (
            "entreprise" in col_clean
            or "societe" in col_clean
            or "etablissement" in col_clean
            or "raison" in col_clean
            or "enseigne" in col_clean
        ):
            mapping["nom_entreprise"] = col
        elif not mapping["adresse"] and "adresse" in col_clean:
            mapping["adresse"] = col
        elif not mapping["ville"] and ("ville" in col_clean or "cp" in col_clean):
            mapping["ville"] = col

    if not mapping["email"]:
        mapping["email"] = df.columns[4] if len(df.columns) > 4 else df.columns[0]
    if not mapping["nom_dirigeant"]:
        mapping["nom_dirigeant"] = df.columns[0]
    if not mapping["nom_entreprise"]:
        mapping["nom_entreprise"] = (
            df.columns[2] if len(df.columns) > 2 else df.columns[0]
        )

    return mapping


# ==========================================
# 4. CONTRÔLE HORAIRE & SMTP
# ==========================================
def verifier_et_attendre_creneau_horaire():
    while True:
        maintenant = datetime.now()
        heure = maintenant.hour

        if heure < PLAGE_ENVOIE[0] or heure >= PLAGE_ENVOIE[1]:
            print(
                f"⏰ Hors plage d'envoi ({maintenant.strftime('%H:%M')}). Pause 10 min..."
            )
            time.sleep(600)
        elif heure == 12:
            print(
                f"🍽️ Pause déjeuner ({maintenant.strftime('%H:%M')}). Pause 5 min..."
            )
            time.sleep(300)
        else:
            break


def envoyer_email(expediteur, destinataire_email, sujet, corps_html):
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{expediteur['prenom']} <{expediteur['email']}>"
        msg["To"] = destinataire_email
        msg["Subject"] = sujet
        msg.attach(MIMEText(corps_html, "html", "utf-8"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(expediteur["email"], expediteur["mot_de_passe"])
        server.send_message(msg)
        server.quit()

        print(f"✅ Mail envoyé via {expediteur['prenom']} à {destinataire_email}")
        return True
    except Exception as e:
        print(f"❌ Erreur d'envoi à {destinataire_email} : {e}")
        return False


def generer_contexte_premier_contact():
    aujourdhui = datetime.now()
    date_appel = (aujourdhui - timedelta(days=random.randint(30, 60))).strftime(
        "%d/%m"
    )
    date_passage = (aujourdhui - timedelta(days=random.randint(30, 90))).strftime(
        "%d/%m"
    )

    options = [
        f"J'ai eu un des membres de votre équipe le {date_appel} par téléphone.",
        f"Je fais suite à mon passage dans votre établissement le {date_passage}.",
    ]
    return random.choice(options)


# ==========================================
# 5. SÉQUENCE PRINCIPALE
# ==========================================
def executer_campagne(chemin_fichier):
    """
    print("🔍 [1/2] Analyse des boîtes mail pour traiter les opt-outs et réponses...")
    try:
        relever_boite_et_appliquer_optout()
    except Exception as e:
        print(f"🛑 Échec de la relève IMAP ({e}). Campagne annulée par sécurité.")
        return
    """
    # ÉTAPE B : Chargement de la base à jour
    print("🚀 [2/2] Démarrage de la séquence d'envoi...")
    df, chemin_fichier = charger_fichier_prospects(chemin_fichier)
    cols = mapper_colonnes_automatiquement(df)

    for c in [
        "Statut",
        "Date_Mail_1",
        "Date_Relance_1",
        "Date_Relance_2",
        "Date_Relance_3",
    ]:
        if c not in df.columns:
            df[c] = None
        df[c] = df[c].astype("object")

    total_expediteurs = len(EXPEDITEURS)
    index_expediteur = 0
    aujourdhui = datetime.now()

    for index, row in df.iterrows():
        verifier_et_attendre_creneau_horaire()

        email_destinataire = (
            str(row[cols["email"]]).strip() if pd.notna(row[cols["email"]]) else None
        )
        if not email_destinataire or "@" not in email_destinataire:
            continue

        statut_actuel = str(row["Statut"]).strip() if pd.notna(row["Statut"]) else ""

        # SÉCURITÉ OPT-OUT & EXCLUSIONS
        if statut_actuel in STATUTS_EXCLUS:
            continue

        d1 = pd.to_datetime(row["Date_Mail_1"]) if pd.notna(row["Date_Mail_1"]) else None
        d2 = (
            pd.to_datetime(row["Date_Relance_1"])
            if pd.notna(row["Date_Relance_1"])
            else None
        )
        d3 = (
            pd.to_datetime(row["Date_Relance_2"])
            if pd.notna(row["Date_Relance_2"])
            else None
        )

        type_action = None
        if statut_actuel in ["", "nan", "Actif", "À contacter"]:
            type_action = "MAIL_1"
        elif statut_actuel == "Mail 1 Envoyé" and d1:
            if (aujourdhui - d1).days >= DELAI_RELANCE_1:
                type_action = "RELANCE_1"
        elif statut_actuel == "Relance 1 Envoyée" and d2:
            if (aujourdhui - d2).days >= DELAI_RELANCE_2:
                type_action = "RELANCE_2"
        elif statut_actuel == "Relance 2 Envoyée" and d3:
            if (aujourdhui - d3).days >= DELAI_RELANCE_3:
                type_action = "RELANCE_3"

        if not type_action:
            continue

        # Rotation des expéditeurs
        expediteur_actuel = None
        for _ in range(total_expediteurs):
            candidat = EXPEDITEURS[index_expediteur % total_expediteurs]
            index_expediteur += 1
            if candidat["envoyes"] < MAX_MAILS_PAR_COMPTE:
                expediteur_actuel = candidat
                break

        if not expediteur_actuel:
            print("\n🛑 Quota quotidien (125 mails) atteint sur tous les comptes.")
            break

        nom_dirigeant = (
            str(row[cols["nom_dirigeant"]]).strip()
            if pd.notna(row[cols["nom_dirigeant"]])
            else ""
        )
        nom_entreprise = (
            str(row[cols["nom_entreprise"]]).strip()
            if pd.notna(row[cols["nom_entreprise"]])
            else "votre établissement"
        )
        politesse = f"Bonjour {nom_dirigeant}" if nom_dirigeant else "Bonjour"

        # PROMPTS IA SÉCURISÉS ET STRUCTURÉS
        if type_action == "MAIL_1":
            contexte_relance = generer_contexte_premier_contact()
            prompt = f"""Tu es {expediteur_actuel['prenom']}, conseiller en énergie.
Rédige un e-mail de prospection B2B court et propre pour : {nom_entreprise}.

STRUCTURE OBLIGATOIRE DU MESSAGE :
Ligne 1 : {politesse},
Ligne 2 : {contexte_relance}
Ligne 3 : L’idée reste simple : en 15 minutes, je vous présenterai notre service de mise en concurrence pour vos contrats électricité/gaz auprès de 30 fournisseurs. Cette démarche est sans frais, sans engagement avec des offres à tarif fixe (nos partenaires constatent en moyenne ~35% d’économies sur leur budget annuel).
Ligne 4 : [BALISE_LIEN]

INTERDICTIONS STRICTES :
- Ne mets RIEN avant "{politesse}".
- N'invente aucun autre texte ou lien après [BALISE_LIEN].
- Arrête-toi immédiatement après [BALISE_LIEN].
"""
            sujet = f"Optimisation énergie - {nom_entreprise}"

        elif type_action == "RELANCE_1":
            prompt = f"""Tu es {expediteur_actuel['prenom']}, conseiller en énergie.
Rédige une relance très courte (2 phrases) pour : {nom_entreprise}.

STRUCTURE OBLIGATOIRE :
{politesse},
Je me permettais de revenir vers vous suite à mon précédent message concernant vos contrats d'énergie.
Avez-vous eu l'opportunité de consulter notre proposition pour faire jouer la concurrence auprès de nos 30 fournisseurs partenaires ?
[BALISE_LIEN]

INTERDICTIONS : Ne rajoute aucun texte après [BALISE_LIEN].
"""
            sujet = f"Re: Optimisation énergie - {nom_entreprise}"

        elif type_action == "RELANCE_2":
            prompt = f"""Tu es {expediteur_actuel['prenom']}, conseiller en énergie.
Rédige une deuxième relance courte pour : {nom_entreprise}.

STRUCTURE OBLIGATOIRE :
{politesse},
Je reviens vers vous car l'optimisation des charges d'électricité et de gaz reste un levier d'économie majeur pour votre secteur.
Un échange de 15 minutes nous permet d'évaluer gratuitement si vos contrats actuels sont surévalués.
[BALISE_LIEN]

INTERDICTIONS : Ne rajoute aucun texte après [BALISE_LIEN].
"""
            sujet = f"Mise en concurrence contrats énergie {nom_entreprise}"

        elif type_action == "RELANCE_3":
            prompt = f"""Tu es {expediteur_actuel['prenom']}, conseiller en énergie.
Rédige un dernier message direct et respectueux pour : {nom_entreprise}.

STRUCTURE OBLIGATOIRE :
{politesse},
Je suppose que la révision de vos contrats d'énergie n'est pas votre priorité actuellement, ou que vous disposez déjà des meilleurs tarifs.
C'est mon dernier message et je ne vous solliciterai plus. Si le sujet devient d'actualité, vous pouvez réserver un créneau ci-dessous :
[BALISE_LIEN]

INTERDICTIONS : Ne rajoute aucun texte après [BALISE_LIEN].
"""
            sujet = f"Dernier essai - {nom_entreprise}"

        # Génération Ollama en streaming
        print(f"\n🤖 Génération IA pour {email_destinataire} ({type_action})...")
        print("=" * 65)
        print(f"📩 DESTINATAIRE : {email_destinataire}")
        print(f"👤 EXPÉDITEUR   : {expediteur_actuel['prenom']} ({expediteur_actuel['email']})")
        print(f"📌 SUJET        : {sujet}")
        print("-" * 65)

        corps_ia = ""
        try:
            stream = ollama.chat(
                model="llama3.2:3b",
                messages=[{"role": "user", "content": prompt}],
                options={
                    "num_predict": 150,
                    "temperature": 0.1,
                    "top_p": 0.3,
                },
                stream=True,
            )

            for chunk in stream:
                mots = chunk["message"]["content"]
                corps_ia += mots

            lignes = corps_ia.splitlines()

            while lignes and not lignes[0].strip().lower().startswith(("bonjour ", "bonjour")):
                lignes.pop(0)

            corps_ia = "\n".join(lignes).strip()

            if "[BALISE_LIEN]" in corps_ia:
                corps_ia = corps_ia.split("[BALISE_LIEN]", 1)[0].rstrip()
                corps_ia += "\n\n[BALISE_LIEN]"
            else:
                corps_ia = corps_ia.rstrip() + "\n\n[BALISE_LIEN]"

        except Exception as e:
            print(f"\n❌ Erreur avec Ollama ({e}). Passage au prospect suivant.\n")
            continue

        # NETTOYAGE DES HALLUCINATIONS EN PYTHON (Sécurité Anti-Boucle)
        if "[BALISE_LIEN]" in corps_ia:
            partie_avant = corps_ia.split("[BALISE_LIEN]")[0]
            corps_ia = partie_avant.strip() + "\n\n[BALISE_LIEN]"

        print(corps_ia)
        print("\n" + "=" * 65 + "\n")

        # Mise en forme HTML
        corps_ia_format = (
            corps_ia.replace("[BALISE_LIEN]", LIEN_HTML_CLIQUABLE)
            if "[BALISE_LIEN]" in corps_ia
            else corps_ia + f"<br><br>{LIEN_HTML_CLIQUABLE}"
        )

        corps_html_formate = corps_ia_format.replace("\n", "<br>")
        signature_html = f"<br><br>{expediteur_actuel['prenom']}<br>{ADRESSE_SIGNATURE}"

        mention_optout_html = """
        <br><br>
        <hr style="border: 0; border-top: 1px solid #eeeeee;" />
        <p style="font-size: 11px; color: #777777; margin-top: 10px;">
            Conformément à la réglementation sur la prospection B2B, si vous ne souhaitez plus recevoir nos propositions d'optimisation énergétique, répondez simplement <strong>STOP</strong> à ce message.
        </p>
        """

        message_final_html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; font-size: 14px; color: #333333;">
            {corps_html_formate}
            {signature_html}
            {mention_optout_html}
          </body>
        </html>
        """

        # Envoi SMTP
        if envoyer_email(expediteur_actuel, email_destinataire, sujet, message_final_html):
            expediteur_actuel["envoyes"] += 1
            date_str = aujourdhui.strftime("%Y-%m-%d %H:%M")

            if type_action == "MAIL_1":
                df.at[index, "Statut"] = "Mail 1 Envoyé"
                df.at[index, "Date_Mail_1"] = date_str
            elif type_action == "RELANCE_1":
                df.at[index, "Statut"] = "Relance 1 Envoyée"
                df.at[index, "Date_Relance_1"] = date_str
            elif type_action == "RELANCE_2":
                df.at[index, "Statut"] = "Relance 2 Envoyée"
                df.at[index, "Date_Relance_2"] = date_str
            elif type_action == "RELANCE_3":
                df.at[index, "Statut"] = "Relance 3 Envoyée"
                df.at[index, "Date_Relance_3"] = date_str

            pause = random.randint(20, 40)
            print(f"⏳ Pause de {pause}s avant le prochain envoi...\n")
            time.sleep(pause)

    # Sauvegarde finale
    if chemin_fichier.endswith(".csv"):
        df.to_csv(chemin_fichier, index=False, sep=";")
    else:
        df.to_excel(chemin_fichier, index=False)

    print(f"\n💾 Base de données sauvegardée dans {chemin_fichier} !")


def main() -> None:
    verifier_et_demarrer_ollama()
    executer_campagne(sys.argv[1])


if __name__ == "__main__":
    try:
        file = sys.argv[1]
        if not file:
            raise IndexError
        main()

    except IndexError:
        print("Usage: make run FILE=<fichier.xlsx>\n"
              "       uv run <python> Main.py <fichier.xlsx>")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Keyboard interrupt.")
        sys.exit(1)
