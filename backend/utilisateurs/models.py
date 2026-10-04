import os
from django.contrib.auth.models import AbstractUser
from django.db import models

def entreprise_logo_path(instance, filename):
  return f'logos/entreprise_{instance.user.id}/{filename}'

def user_cv_path(instance, filename):
  return f'cvs/user_{instance.user.id}/{filename}'


class User(AbstractUser):
  ROLE_CHOICES = (
      ('ETUDIANT', 'Étudiant'),
      ('ENTREPRISE', 'Entreprise'),
      ('ADMIN', 'Admin'),
  )
  role = models.CharField(
      max_length=20, choices=ROLE_CHOICES, default='ETUDIANT'
  )

  def save(self, *args, **kwargs):
    # Un superuser (createsuperuser) reçoit automatiquement le rôle ADMIN
    if self.is_superuser and self.role == 'ETUDIANT':
      self.role = 'ADMIN'
    super().save(*args, **kwargs)

  def __str__(self):
    return f'{self.username} ({self.role})'


class ProfilEtudiant(models.Model):
  user = models.OneToOneField(
      User, on_delete=models.CASCADE, related_name='profil_etudiant'
  )
  telephone = models.CharField(max_length=20, blank=True, null=True)
  formation = models.CharField(
      max_length=255, blank=True, null=True
  )  # Ex: Master Télécommunications et Réseaux
  niveau_etudes = models.CharField(
      max_length=50, blank=True, null=True
  )  # Ex: Bac+5
  competences = models.TextField(
      blank=True, null=True
  )  # Ex: Python, Django, React, Réseaux
  cv = models.FileField(upload_to=user_cv_path, blank=True, null=True)
  date_Mise_a_jour = models.DateTimeField(auto_now=True)

  def __str__(self):
    return f'Profil de {self.user.get_full_name() or self.user.username}'



class ProfilEntreprise(models.Model):
  user = models.OneToOneField(
      User, on_delete=models.CASCADE, related_name='profil_entreprise'
  )
  nom_entreprise = models.CharField(max_length=255)
  secteur = models.CharField(
      max_length=150
  )  # Ex: Technologies de l'information, Finance, Télécoms
  description = models.TextField(
      blank=True, null=True
  )  # Description détaillée de l'entreprise
  logo = models.ImageField(
      upload_to=entreprise_logo_path, blank=True, null=True
  )
  site_web = models.URLField(blank=True, null=True)
  telephone = models.CharField(max_length=20, blank=True, null=True)
  adresse = models.CharField(max_length=255, blank=True, null=True)
  date_mise_a_jour = models.DateTimeField(auto_now=True)

  def __str__(self):
    return f'{self.nom_entreprise} (Secteur: {self.secteur})'    
