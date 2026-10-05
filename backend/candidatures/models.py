import os
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def _chemin(dossier, instance, filename):
  # Nom aléatoire : impossible à deviner. L'accès passe de toute façon par l'API.
  extension = os.path.splitext(filename)[1].lower() or '.pdf'
  return (
      f'candidatures/offre_{instance.offre_id}/etudiant_{instance.etudiant_id}/'
      f'{dossier}_{uuid.uuid4().hex}{extension}'
  )


def candidature_cv_path(instance, filename):
  return _chemin('cv', instance, filename)


def candidature_lettre_path(instance, filename):
  return _chemin('lettre', instance, filename)


class Candidature(models.Model):

  class Statut(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente'
    ACCEPTEE = 'ACCEPTEE', 'Acceptée'
    REFUSEE = 'REFUSEE', 'Refusée'

  etudiant = models.ForeignKey(
      settings.AUTH_USER_MODEL,
      on_delete=models.CASCADE,
      related_name='candidatures',
      limit_choices_to={'role': 'ETUDIANT'},
  )
  # PROTECT : une offre ayant reçu des candidatures ne peut pas être supprimée
  offre = models.ForeignKey(
      'offres.OffreStage', on_delete=models.PROTECT, related_name='candidatures'
  )
  cv = models.FileField(upload_to=candidature_cv_path)
  lettre_motivation = models.FileField(upload_to=candidature_lettre_path)
  message = models.TextField(blank=True, default='')
  statut = models.CharField(
      max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE
  )
  commentaire_entreprise = models.TextField(blank=True, default='')
  date_candidature = models.DateTimeField(auto_now_add=True)
  date_decision = models.DateTimeField(null=True, blank=True)

  class Meta:
    ordering = ['-date_candidature']
    constraints = [
        models.UniqueConstraint(
            fields=['etudiant', 'offre'], name='candidature_unique_par_offre'
        )
    ]

  def __str__(self):
    return f'{self.etudiant.username} → {self.offre.titre} ({self.statut})'


class EvaluationStage(models.Model):
  """Évaluation du stagiaire par l'entreprise (notes sur 20)."""

  candidature = models.OneToOneField(
      Candidature, on_delete=models.CASCADE, related_name='evaluation'
  )
  note_technique = models.PositiveSmallIntegerField(
      validators=[MinValueValidator(0), MaxValueValidator(20)],
      help_text='Compétences techniques (sur 20)',
  )
  note_autonomie = models.PositiveSmallIntegerField(
      validators=[MinValueValidator(0), MaxValueValidator(20)]
  )
  note_communication = models.PositiveSmallIntegerField(
      validators=[MinValueValidator(0), MaxValueValidator(20)]
  )
  note_assiduite = models.PositiveSmallIntegerField(
      validators=[MinValueValidator(0), MaxValueValidator(20)],
      help_text='Assiduité et ponctualité (sur 20)',
  )
  appreciation = models.TextField(blank=True, default='')
  points_forts = models.TextField(blank=True, default='')
  axes_amelioration = models.TextField(blank=True, default='')
  recommande = models.BooleanField(default=False)
  date_evaluation = models.DateTimeField(auto_now_add=True)
  date_modification = models.DateTimeField(auto_now=True)

  @property
  def moyenne(self):
    total = (
        self.note_technique + self.note_autonomie
        + self.note_communication + self.note_assiduite
    )
    return round(total / 4, 2)

  def __str__(self):
    return f'Évaluation de {self.candidature.etudiant.username} ({self.moyenne}/20)'
