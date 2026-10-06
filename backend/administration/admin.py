from django.contrib import admin
from administration.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
  """Journal en lecture seule : personne ne peut le modifier ni l'effacer."""

  list_display = ('date', 'acteur', 'action', 'cible_libelle')
  list_filter = ('action',)
  search_fields = ('cible_libelle', 'acteur__username')

  def has_add_permission(self, request):
    return False

  def has_change_permission(self, request, obj=None):
    return False

  def has_delete_permission(self, request, obj=None):
    return False
