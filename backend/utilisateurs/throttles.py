from rest_framework.throttling import AnonRateThrottle


class ProfilsPublicsThrottle(AnonRateThrottle):
  """Annuaires publics (entreprises, étudiants) : 60 requêtes/minute par adresse IP pour les
  visiteurs anonymes (anti-aspiration). Ne concerne pas les utilisateurs connectés."""
  scope = 'profils_publics'
  rate = '60/min'
