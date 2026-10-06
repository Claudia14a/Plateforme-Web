import logging

from administration.models import AuditLog

logger = logging.getLogger(__name__)


def enregistrer(acteur, action, cible=None, details=None):
  """Ajoute une ligne au journal d'audit. Ne fait jamais échouer l'action métier."""
  try:
    if acteur is not None and not getattr(acteur, 'is_authenticated', False):
      acteur = None
    AuditLog.objects.create(
        acteur=acteur,
        action=action,
        cible_type=cible.__class__.__name__ if cible is not None else '',
        cible_id=getattr(cible, 'pk', None),
        cible_libelle=str(cible)[:255] if cible is not None else '',
        details=details or {},
    )
  except Exception:
    logger.exception("Échec d'écriture du journal d'audit (%s)", action)
