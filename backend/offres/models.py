from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Categorie(models.Model):
  """Catégorie d'offre de stage (ex : Développement web, Marketing, Design...)."""

  nom = models.CharField(max_length=150, unique=True)
  slug = models.SlugField(max_length=160, unique=True, blank=True)
  description = models.TextField(blank=True, default='')

  class Meta:
    ordering = ['nom']
    verbose_name = 'catégorie'
    verbose_name_plural = 'catégories'

  def save(self, *args, **kwargs):
    if not self.slug:
      base = slugify(self.nom) or 'categorie'
      slug, n = base, 2
      while Categorie.objects.filter(slug=slug).exclude(pk=self.pk).exists():
        slug = f'{base}-{n}'
        n += 1
      self.slug = slug
    super().save(*args, **kwargs)

  def __str__(self):
    return self.nom


class OffreStage(models.Model):
  entreprise = models.ForeignKey(
      settings.AUTH_USER_MODEL,
      on_delete=models.CASCADE,
      related_name='offres_publier',
      limit_choices_to={'role': 'ENTREPRISE'},
  )
  # SET_NULL : supprimer une catégorie ne supprime jamais les offres
  categorie = models.ForeignKey(
      Categorie,
      on_delete=models.SET_NULL,
      null=True,
      blank=True,
      related_name='offres',
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
