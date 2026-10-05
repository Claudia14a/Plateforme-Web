from django.contrib import admin
from conventions.models import Convention


@admin.register(Convention)
class ConventionAdmin(admin.ModelAdmin):
  list_display = ('candidature', 'statut', 'date_debut', 'date_fin', 'date_mise_a_jour')
  list_filter = ('statut',)

  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'candidature':
      # Seules les candidatures acceptées peuvent avoir une convention
      from candidatures.models import Candidature
      kwargs['queryset'] = Candidature.objects.filter(statut=Candidature.Statut.ACCEPTEE)
    return super().formfield_for_foreignkey(db_field, request, **kwargs)
