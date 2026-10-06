"""Envoi des notifications : ligne dans l'interface + e-mail (modèle HTML par type d'événement).

Les e-mails sont envoyés de façon synchrone et ne font jamais échouer l'action métier.
Pour de gros volumes, ce module est le seul endroit à brancher sur Celery.
"""
import logging
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string

from notifications.models import Notification

logger = logging.getLogger(__name__)

# Un type d'événement = un sujet d'e-mail, un titre/message pour l'interface,
# un lien (route du front) et un modèle d'e-mail :
# notifications/templates/notifications/emails/<type en minuscules>.html
TYPES = {
    'CANDIDATURE_RECUE': {
        'sujet': 'Nouvelle candidature : {offre_titre}',
        'titre': 'Nouvelle candidature',
        'message': '{etudiant_nom} a postulé à votre offre « {offre_titre} ».',
        'lien': '/entreprise/candidatures/{candidature_id}',
        'email': True,
    },
    'CANDIDATURE_ACCEPTEE': {
        'sujet': 'Candidature acceptée : {offre_titre}',
        'titre': 'Candidature acceptée',
        'message': '{entreprise_nom} a accepté votre candidature pour « {offre_titre} ».',
        'lien': '/etudiant/candidatures/{candidature_id}',
        'email': True,
    },
    'CANDIDATURE_REFUSEE': {
        'sujet': 'Réponse à votre candidature : {offre_titre}',
        'titre': 'Candidature non retenue',
        'message': "{entreprise_nom} n'a pas retenu votre candidature pour « {offre_titre} ».",
        'lien': '/etudiant/candidatures/{candidature_id}',
        'email': True,
    },
    'CONVENTION_A_TRAITER': {
        'sujet': 'Convention à traiter : {numero}',
        'titre': 'Convention à traiter',
        'message': 'La convention {numero} ({etudiant_nom} / {entreprise_nom}) attend votre vérification.',
        'lien': '/admin/conventions/{convention_id}',
        'email': False,  # simple notification dans l'interface pour les administrateurs
    },
    'CONVENTION_PRETE': {
        'sujet': 'Votre convention de stage est prête ({numero})',
        'titre': 'Convention de stage prête',
        'message': 'La convention {numero} pour « {offre_titre} » est validée : vous pouvez la télécharger.',
        'lien': '/conventions/{convention_id}',
        'email': True,
    },
    'CONVENTION_SIGNEE': {
        'sujet': 'Convention de stage signée ({numero})',
        'titre': 'Convention signée',
        'message': 'La convention {numero} pour « {offre_titre} » est signée. Bon stage !',
        'lien': '/conventions/{convention_id}',
        'email': True,
    },
    'ATTESTATION_DISPONIBLE': {
        'sujet': 'Votre attestation de stage est disponible',
        'titre': 'Attestation de stage disponible',
        'message': 'Votre attestation de stage ({offre_titre}) est disponible au téléchargement.',
        'lien': '/conventions/{convention_id}',
        'email': True,
    },
}


def _front_url():
  return getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')


def _html_vers_texte(html):
  texte = re.sub(r'(?is)<(style|head).*?</\1>', '', html)
  texte = re.sub(r'(?i)</(p|div|h1|h2|tr)>|<br\s*/?>', '\n', texte)
  texte = re.sub(r'<[^>]+>', '', texte)
  texte = re.sub(r'[ \t]+', ' ', texte)
  return re.sub(r'\n\s*\n+', '\n\n', texte).strip()


def _envoyer_email(destinataire, type_, config, contexte):
  contexte = dict(contexte)
  contexte['destinataire_nom'] = destinataire.get_full_name() or destinataire.username
  contexte['lien_complet'] = f"{_front_url()}{config['lien'].format(**contexte)}"
  contexte['titre'] = config['titre']
  contexte['message'] = config['message'].format(**contexte)
  html = render_to_string(f'notifications/emails/{type_.lower()}.html', contexte)
  message = EmailMultiAlternatives(
      subject=config['sujet'].format(**contexte),
      body=_html_vers_texte(html),
      from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
      to=[destinataire.email],
  )
  message.attach_alternative(html, 'text/html')
  message.send(fail_silently=False)


def notifier(destinataire, type_, **contexte):
  """Crée la notification dans l'interface et envoie l'e-mail du type d'événement.
  Retourne la Notification, ou None en cas d'échec (jamais d'exception)."""
  try:
    config = TYPES[type_]
    contexte = {k: ('' if v is None else v) for k, v in contexte.items()}
    notification = Notification.objects.create(
        destinataire=destinataire,
        type=type_,
        titre=config['titre'],
        message=config['message'].format(**contexte),
        lien=config['lien'].format(**contexte),
    )
  except Exception:
    logger.exception('Échec de création de la notification %s', type_)
    return None

  if config['email'] and destinataire.email and destinataire.is_active:
    try:
      _envoyer_email(destinataire, type_, config, contexte)
    except Exception:
      logger.exception("Échec d'envoi de l'e-mail %s à %s", type_, destinataire.email)
  return notification


def notifier_admins(type_, **contexte):
  User = get_user_model()
  admins = User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(role='ADMIN'))
  for admin in admins:
    notifier(admin, type_, **contexte)
