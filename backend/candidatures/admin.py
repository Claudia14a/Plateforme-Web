from django.contrib import admin
from candidatures.models import Candidature, EvaluationStage


@admin.register(Candidature)
class CandidatureAdmin(admin.ModelAdmin):
  list_display = ('etudiant', 'offre', 'statut', 'date_candidature', 'date_decision')
  list_filter = ('statut',)
  search_fields = ('etudiant__username', 'offre__titre')


@admin.register(EvaluationStage)
class EvaluationStageAdmin(admin.ModelAdmin):
  list_display = ('candidature', 'moyenne', 'recommande', 'date_evaluation')
