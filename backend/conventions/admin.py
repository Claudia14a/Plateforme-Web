from django.contrib import admin, messages

from conventions import services
from conventions.models import Convention


@admin.register(Convention)
class ConventionAdmin(admin.ModelAdmin):
  """Les conventions sont créées automatiquement quand une entreprise accepte une
  candidature : on ne les crée pas à la main. L'admin corrige le contenu (tant que
  la convention n'est pas validée) et fait avancer le circuit avec les actions ci-dessous."""

  list_display = ('numero', 'candidature', 'statut', 'date_debut', 'date_fin', 'date_mise_a_jour')
  list_filter = ('statut',)
  search_fields = ('numero', 'candidature__etudiant__username', 'candidature__offre__titre')
  readonly_fields = (
      'numero', 'candidature', 'statut', 'fichier', 'fichier_signe', 'attestation',
      'date_attestation', 'valide_par', 'date_validation', 'date_signature',
      'motif_rejet', 'date_creation', 'date_mise_a_jour',
  )
  fields = (
      'numero', 'candidature', 'statut', 'sujet', 'missions', 'lieu', 'date_debut', 'date_fin',
      'fichier', 'fichier_signe', 'attestation', 'date_attestation', 'motif_rejet',
      'valide_par', 'date_validation', 'date_signature', 'date_creation', 'date_mise_a_jour',
  )
  actions = ['action_soumettre', 'action_valider', 'action_signer', 'action_regenerer']

  def has_add_permission(self, request):
    return False

  def save_model(self, request, obj, form, change):
    if change and not obj.est_modifiable:
      messages.error(request, 'Une convention validée ou signée ne peut plus être modifiée.')
      return
    super().save_model(request, obj, form, change)
    if change and form.changed_data:
      services.regenerer_pdf(obj)  # le PDF est rempli à nouveau automatiquement

  def _appliquer(self, request, queryset, fonction, message):
    for convention in queryset:
      try:
        fonction(convention, request.user)
        self.message_user(request, f'{convention.numero} : {message}', messages.SUCCESS)
      except services.TransitionInvalide as erreur:
        self.message_user(request, f'{convention.numero} : {erreur}', messages.ERROR)

  @admin.action(description='Soumettre à validation (brouillon → en attente)')
  def action_soumettre(self, request, queryset):
    self._appliquer(request, queryset, services.soumettre, 'soumise.')

  @admin.action(description='Valider (en attente → validée)')
  def action_valider(self, request, queryset):
    self._appliquer(request, queryset, services.valider, 'validée, étudiant et entreprise prévenus.')

  @admin.action(description='Marquer comme signée (validée → signée)')
  def action_signer(self, request, queryset):
    self._appliquer(request, queryset, services.signer, 'signée.')

  @admin.action(description='Régénérer le PDF (brouillon / en attente)')
  def action_regenerer(self, request, queryset):
    for convention in queryset:
      if convention.est_modifiable:
        services.regenerer_pdf(convention)
        self.message_user(request, f'{convention.numero} : PDF régénéré.', messages.SUCCESS)
      else:
        self.message_user(request, f'{convention.numero} : déjà validée ou signée.', messages.ERROR)
