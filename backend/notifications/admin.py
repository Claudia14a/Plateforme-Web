from django.contrib import admin
from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
  list_display = ('destinataire', 'type', 'titre', 'lue', 'date_creation')
  list_filter = ('type', 'lue')
  search_fields = ('destinataire__username', 'titre')
