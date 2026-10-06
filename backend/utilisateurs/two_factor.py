"""Double authentification par e-mail (code à 6 chiffres à usage unique).

Flux connexion :  login (identifiants OK) -> e-mail avec code -> verify-2fa -> JWT
Flux inscription: register               -> e-mail avec code -> verify-2fa -> compte activé + JWT
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework import exceptions, serializers

from .emails import envoyer_email_code
from .models import CodeVerification, User

LOGIN = 'LOGIN'
REGISTER = 'REGISTER'

SEL_MFA = 'utilisateurs.mfa-challenge'
MFA_TOKEN_VALIDITE = 60 * 30   # le jeton de défi reste valable 30 min (renvoi de code possible)
MAX_TENTATIVES = 5             # essais autorisés par code
DELAI_RENVOI = 60              # secondes minimum entre deux envois (route « renvoyer »)


class EmailIndisponible(exceptions.APIException):
  status_code = 503
  default_detail = "Impossible d'envoyer l'e-mail de vérification pour le moment. Réessayez dans un instant."
  default_code = 'email_indisponible'


def deux_facteurs_actif():
  return getattr(settings, 'TWO_FACTOR_ENABLED', True)


def validite_minutes():
  return getattr(settings, 'TWO_FACTOR_CODE_VALIDITE_MINUTES', 10)


def masquer_email(email):
  """jean.dupont@gmail.com -> j***@gmail.com"""
  local, _, domaine = (email or '').partition('@')
  if not domaine:
    return ''
  return f'{local[:1]}***@{domaine}'


def _hacher(code, user_id, purpose):
  return salted_hmac('utilisateurs.2fa', f'{user_id}:{purpose}:{code}').hexdigest()


# --- Jeton de défi (prouve que l'étape 1 a réussi) ----------------------------

def creer_mfa_token(user, purpose):
  return signing.dumps({'uid': user.pk, 'purpose': purpose}, salt=SEL_MFA)


def lire_mfa_token(token):
  """Retourne (user, purpose) ou lève une ValidationError."""
  try:
    contenu = signing.loads(token, salt=SEL_MFA, max_age=MFA_TOKEN_VALIDITE)
  except signing.SignatureExpired:
    raise serializers.ValidationError(
        {'mfa_token': 'Session de vérification expirée. Reconnectez-vous.'}
    )
  except signing.BadSignature:
    raise serializers.ValidationError({'mfa_token': 'Jeton de vérification invalide.'})
  try:
    user = User.objects.get(pk=contenu['uid'], is_active=True)
  except User.DoesNotExist:
    raise serializers.ValidationError({'mfa_token': 'Jeton de vérification invalide.'})
  if contenu.get('purpose') not in (LOGIN, REGISTER):
    raise serializers.ValidationError({'mfa_token': 'Jeton de vérification invalide.'})
  return user, contenu['purpose']


# --- Code ---------------------------------------------------------------------

def envoyer_code(user, purpose, respecter_delai=False):
  """Génère un nouveau code (les précédents deviennent invalides) et l'envoie par e-mail.

  Retourne True si l'e-mail est parti, False sinon.
  respecter_delai=True : refuse (429) si un code a été envoyé il y a moins de DELAI_RENVOI s.
  """
  if respecter_delai:
    dernier = CodeVerification.objects.filter(user=user, purpose=purpose).first()
    if dernier:
      ecoule = (timezone.now() - dernier.created_at).total_seconds()
      if ecoule < DELAI_RENVOI:
        attente = int(DELAI_RENVOI - ecoule) + 1
        raise exceptions.Throttled(
            wait=attente,
            detail=f'Patientez {attente} s avant de demander un nouveau code.',
        )

  CodeVerification.objects.filter(user=user, purpose=purpose, utilise=False).update(utilise=True)

  code = f'{secrets.randbelow(10 ** 6):06d}'
  CodeVerification.objects.create(
      user=user,
      purpose=purpose,
      code_hash=_hacher(code, user.pk, purpose),
      expires_at=timezone.now() + timedelta(minutes=validite_minutes()),
  )
  return envoyer_email_code(user, code, purpose, validite_minutes())


def verifier_code(user, purpose, code):
  """Valide le code saisi (usage unique, expiration, nombre d'essais limité)."""
  defi = CodeVerification.objects.filter(user=user, purpose=purpose, utilise=False).first()
  if defi is None or defi.expires_at < timezone.now():
    raise serializers.ValidationError({'code': 'Code expiré. Demandez un nouveau code.'})

  if defi.tentatives >= MAX_TENTATIVES:
    CodeVerification.objects.filter(pk=defi.pk).update(utilise=True)
    raise serializers.ValidationError(
        {'code': 'Trop de tentatives. Demandez un nouveau code.'}
    )

  if not constant_time_compare(defi.code_hash, _hacher(code, user.pk, purpose)):
    CodeVerification.objects.filter(pk=defi.pk).update(tentatives=F('tentatives') + 1)
    raise serializers.ValidationError({'code': 'Code incorrect.'})

  CodeVerification.objects.filter(pk=defi.pk).update(utilise=True)
