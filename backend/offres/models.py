from django.conf import settings
from django.db import models


class OffreStage(models.Model):
  entreprise = models.ForeignKey(
      settings.AUTH_USER_MODEL,
      on_delete=models.CASCADE,
      related_name='offres_publier',
      limit_choices_to={'role': 'ENTREPRISE'},
  )
  titre = models.CharField(max_length=255)
  description = models.TextField()
  domaine = models.CharField(
      max_length=150
  )  
  ville = models.CharField(max_length=100)
  duree_mois = models.PositiveIntegerField()  
  competences_requises = models.TextField(
      help_text='Compétences séparées par des virgules (ex: Python, React, Django)'
  )
  date_limite = models.DateField()
  date_creation = models.DateTimeField(auto_now_add=True)
  active = models.BooleanField(
      default=True
  )  

  def __str__(self):
    return f'{self.titre} — {self.entreprise.username} ({self.ville})'


