"""Réactions automatiques aux changements d'une candidature :
- nouvelle candidature  -> l'entreprise est notifiée
- candidature acceptée  -> la convention est créée et remplie automatiquement, l'étudiant est notifié
- candidature refusée   -> l'étudiant est notifié
Chaque décision est enregistrée dans le journal d'audit.
Fonctionne aussi bien depuis l'API que depuis /admin/."""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from candidatures.models import Candidature

logger = logging.getLogger(__name__)


def _contexte(candidature):
  user = candidature.offre.entreprise
  profil = getattr(user, 'profil_entreprise', None)
  return {
      'candidature_id': candidature.pk,
      'offre_titre': candidature.offre.titre,
      'etudiant_nom': candidature.etudiant.get_full_name() or candidature.etudiant.username,
      'entreprise_nom': profil.nom_entreprise if profil else user.username,
      'commentaire': candidature.commentaire_entreprise,
  }


@receiver(pre_save, sender=Candidature)
def memoriser_ancien_statut(sender, instance, **kwargs):
  instance._ancien_statut = (
      Candidature.objects.filter(pk=instance.pk).values_list('statut', flat=True).first()
      if instance.pk else None
  )


@receiver(post_save, sender=Candidature)
def reagir_au_changement(sender, instance, created, raw=False, **kwargs):
  if raw:
    return
  # imports ici pour éviter les dépendances circulaires au démarrage
  from administration import audit
  from conventions.services import creer_convention
  from notifications.services import notifier

  acteur = getattr(instance, '_acteur', None)
  contexte = _contexte(instance)

  if created:
    notifier(instance.offre.entreprise, 'CANDIDATURE_RECUE', **contexte)
    return

  ancien = getattr(instance, '_ancien_statut', None)
  if ancien == instance.statut:
    return

  if instance.statut == Candidature.Statut.ACCEPTEE:
    audit.enregistrer(acteur, 'CANDIDATURE_ACCEPTEE', instance, {'commentaire': instance.commentaire_entreprise})
    try:
      creer_convention(
          instance, date_debut=getattr(instance, '_date_debut_souhaitee', None), acteur=acteur
      )
    except Exception:
      # L'acceptation ne doit jamais échouer à cause du PDF : l'admin pourra relancer la génération
      logger.exception('Création automatique de la convention impossible (candidature %s)', instance.pk)
    notifier(instance.etudiant, 'CANDIDATURE_ACCEPTEE', **contexte)
  elif instance.statut == Candidature.Statut.REFUSEE:
    audit.enregistrer(acteur, 'CANDIDATURE_REFUSEE', instance, {'commentaire': instance.commentaire_entreprise})
    notifier(instance.etudiant, 'CANDIDATURE_REFUSEE', **contexte)
