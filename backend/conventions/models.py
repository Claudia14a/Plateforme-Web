import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def _chemin(prefixe, instance, filename):
  extension = os.path.splitext(filename)[1].lower() or '.pdf'
  return f'conventions/candidature_{instance.candidature_id}/{prefixe}_{uuid.uuid4().hex}{extension}'


def convention_path(instance, filename):
  return _chemin('convention', instance, filename)


def convention_signee_path(instance, filename):
  return _chemin('signee', instance, filename)


def attestation_path(instance, filename):
  return _chemin('attestation', instance, filename)


class Convention(models.Model):
  """Convention de stage liée à une candidature acceptée.

  Elle est créée AUTOMATIQUEMENT quand l'entreprise accepte la candidature
  (statut BROUILLON, PDF généré à partir du modèle), puis suit le circuit :
  BROUILLON -> EN_ATTENTE -> VALIDEE -> SIGNEE.
  """

  class Statut(models.TextChoices):
    BROUILLON = 'BROUILLON', 'Brouillon'
    EN_ATTENTE = 'EN_ATTENTE', 'En attente de validation'
    VALIDEE = 'VALIDEE', 'Validée'
    SIGNEE = 'SIGNEE', 'Signée'

  candidature = models.OneToOneField(
      'candidatures.Candidature', on_delete=models.CASCADE, related_name='convention'
  )
  numero = models.CharField(max_length=30, unique=True, null=True, blank=True)
  statut = models.CharField(
      max_length=20, choices=Statut.choices, default=Statut.BROUILLON
  )

  # Contenu rempli automatiquement depuis l'offre, corrigeable tant que non validée
  sujet = models.CharField(max_length=255, blank=True, default='')
  missions = models.TextField(blank=True, default='')
  lieu = models.CharField(max_length=150, blank=True, default='')
  date_debut = models.DateField(null=True, blank=True)
  date_fin = models.DateField(null=True, blank=True)

  # Documents
  fichier = models.FileField(upload_to=convention_path, blank=True, null=True)
  fichier_signe = models.FileField(upload_to=convention_signee_path, blank=True, null=True)
  attestation = models.FileField(upload_to=attestation_path, blank=True, null=True)
  date_attestation = models.DateTimeField(null=True, blank=True)

  # Circuit de validation
  motif_rejet = models.TextField(blank=True, default='')
  valide_par = models.ForeignKey(
      settings.AUTH_USER_MODEL, null=True, blank=True,
      on_delete=models.SET_NULL, related_name='conventions_validees',
  )
  date_validation = models.DateTimeField(null=True, blank=True)
  date_signature = models.DateTimeField(null=True, blank=True)

  date_creation = models.DateTimeField(auto_now_add=True)
  date_mise_a_jour = models.DateTimeField(auto_now=True)

  @property
  def est_telechargeable(self):
    return bool(self.fichier or self.fichier_signe) and self.statut in (
        self.Statut.VALIDEE, self.Statut.SIGNEE,
    )

  @property
  def est_modifiable(self):
    return self.statut in (self.Statut.BROUILLON, self.Statut.EN_ATTENTE)

  @property
  def est_en_cours(self):
    """Stage en cours : convention signée et date du jour comprise entre début et fin."""
    if self.statut != self.Statut.SIGNEE or not (self.date_debut and self.date_fin):
      return False
    return self.date_debut <= timezone.localdate() <= self.date_fin

  def __str__(self):
    return f'Convention {self.numero or self.pk} ({self.statut})'
