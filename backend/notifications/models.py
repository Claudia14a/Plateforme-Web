from django.conf import settings
from django.db import models


class Notification(models.Model):
  """Notification affichée dans l'interface (badge + liste)."""

  class Type(models.TextChoices):
    CANDIDATURE_RECUE = 'CANDIDATURE_RECUE', 'Candidature reçue'
    CANDIDATURE_ACCEPTEE = 'CANDIDATURE_ACCEPTEE', 'Candidature acceptée'
    CANDIDATURE_REFUSEE = 'CANDIDATURE_REFUSEE', 'Candidature refusée'
    CONVENTION_A_TRAITER = 'CONVENTION_A_TRAITER', 'Convention à traiter'
    CONVENTION_PRETE = 'CONVENTION_PRETE', 'Convention prête'
    CONVENTION_SIGNEE = 'CONVENTION_SIGNEE', 'Convention signée'
    ATTESTATION_DISPONIBLE = 'ATTESTATION_DISPONIBLE', 'Attestation disponible'

  destinataire = models.ForeignKey(
      settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
  )
  type = models.CharField(max_length=40, choices=Type.choices)
  titre = models.CharField(max_length=200)
  message = models.TextField()
  lien = models.CharField(max_length=255, blank=True, default='')
  lue = models.BooleanField(default=False)
  date_creation = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['-date_creation', '-id']
    indexes = [models.Index(fields=['destinataire', 'lue'])]

  def __str__(self):
    return f'{self.destinataire} — {self.titre}'
