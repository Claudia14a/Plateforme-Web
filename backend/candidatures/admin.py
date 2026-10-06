from django.contrib import admin, messages
from candidatures.models import Candidature, EvaluationStage


@admin.register(Candidature)
class CandidatureAdmin(admin.ModelAdmin):
  list_display = ('etudiant', 'offre', 'statut', 'date_candidature', 'date_decision')
  list_filter = ('statut',)
  search_fields = ('etudiant__username', 'offre__titre')
  actions = ['generer_convention']

  def save_model(self, request, obj, form, change):
    obj._acteur = request.user  # tracé dans le journal d'audit
    super().save_model(request, obj, form, change)

  @admin.action(description='Générer la convention (candidatures acceptées)')
  def generer_convention(self, request, queryset):
    from conventions.services import creer_convention
    for candidature in queryset:
      if candidature.statut != Candidature.Statut.ACCEPTEE:
        self.message_user(request, f'{candidature} : pas acceptée.', messages.WARNING)
        continue
      convention, creee = creer_convention(candidature, acteur=request.user)
      self.message_user(
          request, f'{convention.numero} : {"créée" if creee else "existait déjà"}.', messages.SUCCESS
      )


@admin.register(EvaluationStage)
class EvaluationStageAdmin(admin.ModelAdmin):
  list_display = ('candidature', 'moyenne', 'recommande', 'date_evaluation')
