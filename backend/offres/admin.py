from django.contrib import admin
from offres.models import Categorie, OffreStage


def _libelle_entreprise(user):
  profil = getattr(user, 'profil_entreprise', None)
  return profil.nom_entreprise if profil else user.username


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
  list_display = ('nom', 'slug')
  search_fields = ('nom',)
  prepopulated_fields = {'slug': ('nom',)}


@admin.register(OffreStage)
class OffreStageAdmin(admin.ModelAdmin):
  list_display = ('titre', 'entreprise_nom', 'categorie', 'ville', 'duree_mois', 'date_limite', 'active')
  list_filter = ('active', 'categorie', 'ville', 'domaine')
  search_fields = ('titre', 'domaine', 'ville')

  @admin.display(description='Entreprise')
  def entreprise_nom(self, obj):
    return _libelle_entreprise(obj.entreprise)

  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    field = super().formfield_for_foreignkey(db_field, request, **kwargs)
    if db_field.name == 'entreprise':
      # La liste déroulante affiche le nom de l'entreprise au lieu de « avenir (ENTREPRISE) »
      field.label_from_instance = _libelle_entreprise
    return field
