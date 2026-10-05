import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)

SEL_VERIFICATION = 'utilisateurs.verification-email'
VERIFICATION_VALIDITE = 60 * 60 * 48  # 48 heures


def _front_url():
  return getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')


def _envoyer(sujet, message, destinataire):
  """Envoie un e-mail sans jamais faire échouer la requête (SMTP indisponible, etc.)."""
  try:
    send_mail(sujet, message, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [destinataire])
    return True
  except Exception:
    logger.exception("Échec d'envoi d'e-mail à %s", destinataire)
    return False


# --- Vérification d'e-mail ---------------------------------------------------

def creer_token_verification(user):
  return signing.dumps({'uid': user.pk, 'email': user.email}, salt=SEL_VERIFICATION)


def lire_token_verification(token):
  """Retourne le contenu du token ou lève signing.BadSignature / SignatureExpired."""
  return signing.loads(token, salt=SEL_VERIFICATION, max_age=VERIFICATION_VALIDITE)


def envoyer_email_verification(user):
  lien = f'{_front_url()}/verifier-email?token={creer_token_verification(user)}'
  message = (
      f'Bonjour {user.get_full_name() or user.username},\n\n'
      "Merci de votre inscription sur la plateforme de gestion des stages.\n"
      f'Pour activer votre compte, confirmez votre adresse e-mail :\n{lien}\n\n'
      'Ce lien est valable 48 heures. Si vous n\'êtes pas à l\'origine de cette '
      'inscription, ignorez ce message.'
  )
  return _envoyer('Confirmez votre adresse e-mail', message, user.email)


# --- Réinitialisation du mot de passe ---------------------------------------

def envoyer_email_reinitialisation(user):
  uid = urlsafe_base64_encode(force_bytes(user.pk))
  token = default_token_generator.make_token(user)
  lien = f'{_front_url()}/reinitialiser-mot-de-passe?uid={uid}&token={token}'
  message = (
      f'Bonjour {user.get_full_name() or user.username},\n\n'
      f'Pour choisir un nouveau mot de passe, ouvrez ce lien :\n{lien}\n\n'
      "Si vous n'avez pas demandé cette réinitialisation, ignorez ce message : "
      'votre mot de passe actuel reste valable.'
  )
  return _envoyer('Réinitialisation de votre mot de passe', message, user.email)
