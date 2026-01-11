import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import os
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class SyndicAlerter:
    def __init__(self, config_path="assets/config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        
        # Configuration SMTP (Pour Gmail: smtp.gmail.com, 587)
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        
        # L'expéditeur est récupéré depuis config.json ("vous" -> "email")
        # Si non trouvé, fallback sur variable d'env ou défaut
        self.sender_email = self.config.get("vous", {}).get("email") or os.getenv("SMTP_USER", "votre_email@gmail.com")
        
        # Le mot de passe DOIT être fourni via variable d'environnement pour la sécurité
        # Pour Gmail, il faut un "Mot de passe d'application" (App Password) si la 2FA est activée
        self.smtp_password = os.getenv("SMTP_PASSWORD", "simulation")

    def _load_config(self):
        """Charge la configuration depuis le fichier JSON"""
        try:
            # Tentative de résolution du chemin
            path = Path(self.config_path)
            if not path.exists():
                # Fallback: chemin relatif depuis ce fichier
                path = Path(__file__).parent.parent.parent / "assets" / "config.json"
            
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Erreur chargement config: {e}")
            return {}

    def send_alert(self, building_name, issue_details, duration_hours):
        """
        Envoie une alerte au syndic configuré dans config.json
        """
        # Récupérer l'email du syndic depuis la config
        syndic_email = self.config.get("syndicat", {}).get("email")
        
        if not syndic_email or "@" not in syndic_email:
            logger.warning("Email syndic introuvable dans config.json ou invalide.")
            return False

        # Lien Google Calendar (Simulé ou réel)
        calendar_link = "https://calendar.google.com/calendar/u/0/r/eventedit?text=Intervention+Qualite+Air+Urgent"

        subject = f"URGENT: Alerte Qualité d'Air - {building_name}"
        
        body = f"""
        Bonjour,

        Ceci est une alerte automatique du système IAQverse.

        Bâtiment : {building_name}
        Durée de l'incident : > {duration_hours} heures
        
        Détails techniques :
        {issue_details}

        Les actions correctives automatiques n'ont pas suffi.
        Merci de planifier une intervention d'urgence via ce lien :
        {calendar_link}

        Cordialement,
        {self.config.get("vous", {}).get("prenom", "L'équipe")} {self.config.get("vous", {}).get("nom", "IAQverse")}
        """

        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = syndic_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            # Simulation si pas de mot de passe configuré (Mode Démo PFE)
            if self.smtp_password == "simulation":
                logger.info("--- SIMULATION ENVOI EMAIL SYNDIC (Mode Simulation) ---")
                logger.info(f"From: {self.sender_email}")
                logger.info(f"To: {syndic_email}")
                logger.info(f"Subject: {subject}")
                logger.info(f"Body:\n{body}")
                logger.info("-------------------------------------------------------------------")
                print(f"SIMULATION EMAIL ENVOYÉ À {syndic_email}") # Print pour voir dans la console directement
                print("-" * 20)
                print(f"OBJET: {subject}")
                print(f"CORPS:\n{body}")
                print("-" * 20)
                return True

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            # Authentification avec l'email de l'expéditeur et le mot de passe d'application
            server.login(self.sender_email, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.sender_email, syndic_email, text)
            server.quit()
            logger.info(f"✅ Email d'alerte envoyé avec succès de {self.sender_email} à {syndic_email}")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'envoi de l'email : {e}")
            return False
