import email
import glob
import imaplib
import re
import smtplib
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd

from config import COMPTES_IMAP, SMTP_SERVER, SMTP_PORT, IMAP_SERVER

# --- LIEN CALENDLY : à remplacer par ton lien réel ---
URL_CALENDLY = "https://calendly.com/a-mirabel-stratenergies/analyse-de-vos-besoins-energetiques-audit-gratuit"
LIEN_HTML_CLIQUABLE = f'<a href="{URL_CALENDLY}">👉 Réserver un créneau ici</a>'
ADRESSE_SIGNATURE = "50 chemin des pradels, Fuveau, 13710"

MOTS_CLES_STOP = [
    "stop",
    "désinscription",
    "desinscription",
    "désabonner",
    "desabonner",
    "ne plus me contacter",
    "pas intéressé",
    "pas interesse",
    "retirer",
]

# Marqueurs d'intérêt positif déclenchant l'envoi automatique du lien Calendly
MOTS_CLES_INTERESSE = [
    "intéressé",
    "interesse",
    "intéressée",
    "interessee",
    "je suis partant",
    "partant",
    "ça m'intéresse",
    "ca m'interesse",
    "oui",
    "avec plaisir",
    "volontiers",
    "quand pouvons-nous",
    "quand pouvons nous",
    "disponible",
    "envoyez-moi",
    "envoyez moi",
    "rendez-vous",
    "rendez vous",
]


def charger_fichier_prospects():
    """Détecte et charge le fichier Excel ou CSV présent dans le dossier."""
    fichiers = glob.glob("*.xlsx") + glob.glob("*.csv") + glob.glob("*.xls")
    fichiers = [f for f in fichiers if not f.startswith("~$")]
    if not fichiers:
        return None, None

    fichier_cible = fichiers[0]
    if fichier_cible.endswith(".csv"):
        try:
            df = pd.read_csv(fichier_cible, sep=";")
        except Exception:
            df = pd.read_csv(fichier_cible, sep=",")
    else:
        df = pd.read_excel(fichier_cible)

    return df, fichier_cible


def decoller_payload_robuste(part):
    """Extrait le texte en gérant proprement le charset du mail."""
    charset = part.get_content_charset() or "utf-8"
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("latin-1", errors="replace")


def nettoyer_citations(corps_texte):
    """Tronque le texte pour ne garder que la nouvelle réponse et ignorer l'historique cité."""
    lignes = corps_texte.splitlines()
    lignes_propres = []

    patterns_citation = [
        r"^---+original message---+",
        r"^le\s+.*\s+a\s+écrit\s*:",
        r"^on\s+.*\s+wrote\s*:",
        r"^de\s*:",
        r"^from\s*:",
    ]

    for ligne in lignes:
        l_strip = ligne.strip().lower()
        if any(re.search(p, l_strip) for p in patterns_citation):
            break
        if l_strip.startswith(">"):
            continue
        lignes_propres.append(ligne)

    return "\n".join(lignes_propres)


def est_reponse_automatique(msg):
    """Détecte si le mail provient d'un répondeur automatique (absences, bot)."""
    auto_submitted = msg.get("Auto-Submitted", "").lower()
    if auto_submitted and auto_submitted != "no":
        return True

    x_autoreply = msg.get("X-Autoreply", "").lower()
    if x_autoreply in ["yes", "true"]:
        return True

    precedence = msg.get("Precedence", "").lower()
    if precedence in ["auto_reply", "bulk", "junk"]:
        return True

    subject = str(msg.get("Subject", "")).lower()
    motifs_absence_sujet = [
        "auto:",
        "autoreply",
        "out of office",
        "réponse automatique",
        "reponse automatique",
        "avis d'absence",
        "en congé",
        "en conges",
        "automatische antwort",
    ]

    return any(motif in subject for motif in motifs_absence_sujet)


def envoyer_reponse_calendly(compte_expediteur, destinataire_email, nom_dirigeant, sujet_origine):
    """Envoie une réponse automatique avec le lien Calendly à un prospect intéressé."""
    politesse = f"Bonjour {nom_dirigeant}" if nom_dirigeant else "Bonjour"
    sujet = f"Re: {sujet_origine}" if sujet_origine else "Votre demande de créneau"

    corps_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; font-size: 14px; color: #333333;">
        {politesse},<br><br>
        Ravi de votre intérêt ! Vous pouvez choisir directement le créneau qui vous convient le mieux :<br><br>
        {LIEN_HTML_CLIQUABLE}<br><br>
        À très vite,<br>
        {compte_expediteur['prenom']}<br>
        {ADRESSE_SIGNATURE}
      </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{compte_expediteur['prenom']} <{compte_expediteur['email']}>"
        msg["To"] = destinataire_email
        msg["Subject"] = sujet
        msg.attach(MIMEText(corps_html, "html", "utf-8"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(compte_expediteur["email"], compte_expediteur["mot_de_passe"])
        server.send_message(msg)
        server.quit()

        print(f"   📅 Lien Calendly envoyé -> {destinataire_email}")
        return True
    except Exception as e:
        print(f"   ❌ Échec envoi Calendly à {destinataire_email} : {e}")
        return False


def relever_boite_et_appliquer_optout():
    """Parcourt les boîtes mail IMAP pour détecter les Opt-Out, les réponses, et envoyer le lien Calendly aux intéressés."""
    df, chemin_fichier = charger_fichier_prospects()

    if df is None:
        print("⚠️ Aucun fichier de prospects trouvé pour le traitement des retours.")
        return

    col_email = next(
        (c for c in df.columns if "email" in str(c).lower() or "mail" in str(c).lower()),
        None,
    )
    if not col_email:
        print("❌ Impossible de trouver la colonne Email dans le fichier.")
        return

    # Colonne dirigeant, pour personnaliser la réponse Calendly (optionnelle)
    col_dirigeant = next(
        (c for c in df.columns if "dirigeant" in str(c).lower() or "prenom" in str(c).lower() or "contact" in str(c).lower()),
        None,
    )

    if "Statut" not in df.columns:
        df["Statut"] = "Actif"

    modifications_compteur = 0

    for compte in COMPTES_IMAP:
        print(f"📬 Inspection IMAP : {compte['email']}...")
        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(compte["email"], compte["mot_de_passe"])
            mail.select("inbox")

            status, messages = mail.search(None, "UNSEEN")
            email_ids = messages[0].split()

            if not email_ids:
                print("   └─ 0 nouveau message.")
                mail.logout()
                continue

            print(f"   └─ {len(email_ids)} message(s) non lu(s) détecté(s).")

            for e_id in email_ids:
                _, msg_data = mail.fetch(e_id, "(BODY.PEEK[])")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        if est_reponse_automatique(msg):
                            print("   🤖 Répondeur automatique détecté (ignoré).")
                            mail.store(e_id, "+FLAGS", "\\Seen")
                            continue

                        expediteur = msg.get("From", "")
                        mail_expediteur = (
                            email.utils.parseaddr(expediteur)[1].lower().strip()
                        )

                        sujet = ""
                        if msg["Subject"]:
                            sujet_decode, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(sujet_decode, bytes):
                                charset_sujet = encoding or "utf-8"
                                try:
                                    sujet = sujet_decode.decode(charset_sujet, errors="replace")
                                except LookupError:
                                    sujet = sujet_decode.decode("latin-1", errors="replace")
                            else:
                                sujet = str(sujet_decode)

                        corps_brut = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    corps_brut += decoller_payload_robuste(part)
                        else:
                            corps_brut = decoller_payload_robuste(msg)

                        corps_propre = nettoyer_citations(corps_brut)
                        texte_analyse = f"{sujet} {corps_propre}".lower()

                        if mail_expediteur:
                            masque = (
                                df[col_email]
                                .astype(str)
                                .str.lower()
                                .str.strip()
                                == mail_expediteur
                            )

                            if masque.any():
                                statut_actuel = df.loc[masque, "Statut"].values[0]
                                extrait_log = corps_propre.replace("\n", " ")[:80]

                                # 1. OPT-OUT — priorité absolue
                                if any(mot in texte_analyse for mot in MOTS_CLES_STOP):
                                    df.loc[masque, "Statut"] = "Désinscrit"
                                    modifications_compteur += 1
                                    print(
                                        f"   🚫 OPT-OUT -> {mail_expediteur} | Extrait: \"{extrait_log}...\""
                                    )

                                # 2. INTÉRÊT POSITIF -> envoi automatique du lien Calendly
                                elif (
                                    statut_actuel not in ["Désinscrit", "Stop", "Intéressé - Calendly Envoyé"]
                                    and any(mot in texte_analyse for mot in MOTS_CLES_INTERESSE)
                                ):
                                    nom_dirigeant = ""
                                    if col_dirigeant:
                                        val = df.loc[masque, col_dirigeant].values[0]
                                        nom_dirigeant = str(val).strip() if pd.notna(val) else ""

                                    envoi_ok = envoyer_reponse_calendly(
                                        compte, mail_expediteur, nom_dirigeant, sujet
                                    )

                                    if envoi_ok:
                                        df.loc[masque, "Statut"] = "Intéressé - Calendly Envoyé"
                                    else:
                                        # Si l'envoi échoue, on marque quand même la détection
                                        # pour qu'un humain vérifie manuellement.
                                        df.loc[masque, "Statut"] = "Intéressé - À Relancer Manuellement"
                                    modifications_compteur += 1
                                    print(
                                        f"   🎯 INTÉRÊT détecté -> {mail_expediteur} | Extrait: \"{extrait_log}...\""
                                    )

                                # 3. AUTRE RÉPONSE HUMAINE (ni stop, ni intérêt explicite)
                                elif statut_actuel not in ["Désinscrit", "Stop", "A Répondu"]:
                                    df.loc[masque, "Statut"] = "A Répondu"
                                    modifications_compteur += 1
                                    print(
                                        f"   💬 RÉPONSE -> {mail_expediteur} | Extrait: \"{extrait_log}...\""
                                    )

                        mail.store(e_id, "+FLAGS", "\\Seen")

            mail.logout()

        except Exception as e:
            print(f"   ⚠️ Erreur d'accès IMAP pour {compte['email']} : {e}")

    if modifications_compteur > 0:
        if chemin_fichier.endswith(".csv"):
            df.to_csv(chemin_fichier, index=False, sep=";")
        else:
            df.to_excel(chemin_fichier, index=False)
        print(
            f"\n💾 {modifications_compteur} statut(s) mis à jour dans {chemin_fichier}.\n"
        )
    else:
        print("✅ Aucun changement de statut nécessaire.\n")


if __name__ == "__main__":
    relever_boite_et_appliquer_optout()