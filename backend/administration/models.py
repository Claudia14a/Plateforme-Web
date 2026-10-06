from django.conf import settings
from django.db import models


class AuditLog(models.Model):
  """Journal d'audit : trace des actions importantes (validations, changements de statut...)."""

  acteur = models.ForeignKey(
      settings.AUTH_USER_MODEL, null=True, blank=True,
      on_delete=models.SET_NULL, related_name='actions_audit',
  )
  action = models.CharField(max_length=60, db_index=True)
  cible_type = models.CharField(max_length=60, blank=True, default='')
  cible_id = models.PositiveBigIntegerField(null=True, blank=True)
  cible_libelle = models.CharField(max_length=255, blank=True, default='')
  details = models.JSONField(default=dict, blank=True)
  date = models.DateTimeField(auto_now_add=True, db_index=True)

  class Meta:
    ordering = ['-date', '-id']

  def __str__(self):
    return f'{self.date:%d/%m/%Y %H:%M} {self.action} {self.cible_libelle}'
