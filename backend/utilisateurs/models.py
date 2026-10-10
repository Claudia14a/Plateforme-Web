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

  # False à l'inscription publique ; True pour les comptes existants ou créés par un admin
  email_verifie = models.BooleanField(default=True)

  def save(self, *args, **kwargs):
    if self.is_superuser and self.role == 'ETUDIANT':
      self.role = 'ADMIN'
    if self.is_superuser:
      self.email_verifie = True
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
  # Apparaît dans l'annuaire public des étudiants (prénom + initiale, formation, niveau,
  # compétences uniquement : jamais l'e-mail, le téléphone ni le CV). L'étudiant peut le désactiver.
  profil_public = models.BooleanField(default=True)
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


class CodeVerification(models.Model):
  """Code à usage unique (6 chiffres) envoyé par e-mail : double authentification
  à la connexion (LOGIN) et confirmation de l'adresse à l'inscription (REGISTER).
  Le code n'est jamais stocké en clair : seule son empreinte (HMAC) l'est."""

  PURPOSE_CHOICES = (
      ('LOGIN', 'Connexion'),
      ('REGISTER', 'Inscription'),
  )

  user = models.ForeignKey(
      User, on_delete=models.CASCADE, related_name='codes_verification'
  )
  purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
  code_hash = models.CharField(max_length=64)
  created_at = models.DateTimeField(auto_now_add=True)
  expires_at = models.DateTimeField()
  tentatives = models.PositiveSmallIntegerField(default=0)
  utilise = models.BooleanField(default=False)

  class Meta:
    ordering = ['-created_at']

  def __str__(self):
    return f'{self.purpose} - {self.user.username} ({self.created_at:%d/%m/%Y %H:%M})'
