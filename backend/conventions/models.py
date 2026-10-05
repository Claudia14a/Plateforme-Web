import os
import uuid

from django.db import models


def convention_path(instance, filename):
  extension = os.path.splitext(filename)[1].lower() or '.pdf'
  return f'conventions/candidature_{instance.candidature_id}/convention_{uuid.uuid4().hex}{extension}'


class Convention(models.Model):
  """Convention de stage liée à une candidature acceptée.

  Pour l'instant le PDF est déposé par un administrateur (interface /admin/).
  La génération automatique à partir d'un modèle sera ajoutée avec le module Administration.
  """

  class Statut(models.TextChoices):
    BROUILLON = 'BROUILLON', 'Brouillon'
    EN_ATTENTE = 'EN_ATTENTE', 'En attente de validation'
    VALIDEE = 'VALIDEE', 'Validée'
    SIGNEE = 'SIGNEE', 'Signée'

  candidature = models.OneToOneField(
      'candidatures.Candidature', on_delete=models.CASCADE, related_name='convention'
  )
  statut = models.CharField(
      max_length=20, choices=Statut.choices, default=Statut.BROUILLON
  )
  date_debut = models.DateField(null=True, blank=True)
  date_fin = models.DateField(null=True, blank=True)
  fichier = models.FileField(upload_to=convention_path, blank=True, null=True)
  date_creation = models.DateTimeField(auto_now_add=True)
  date_mise_a_jour = models.DateTimeField(auto_now=True)

  @property
  def est_telechargeable(self):
    return bool(self.fichier) and self.statut in (self.Statut.VALIDEE, self.Statut.SIGNEE)

  def __str__(self):
    return f'Convention {self.candidature} ({self.statut})'
