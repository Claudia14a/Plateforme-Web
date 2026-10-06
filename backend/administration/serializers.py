from django.contrib.auth import get_user_model
from rest_framework import serializers
from administration.models import AuditLog

User = get_user_model()


class UtilisateurAdminSerializer(serializers.ModelSerializer):
  class Meta:
    model = User
    fields = (
        'id', 'username', 'email', 'first_name', 'last_name', 'role',
        'is_active', 'email_verifie', 'date_joined', 'last_login',
    )
    read_only_fields = fields


class AuditLogSerializer(serializers.ModelSerializer):
  acteur_nom = serializers.CharField(source='acteur.username', read_only=True, default=None)

  class Meta:
    model = AuditLog
    fields = (
        'id', 'date', 'acteur', 'acteur_nom', 'action',
        'cible_type', 'cible_id', 'cible_libelle', 'details',
    )
    read_only_fields = fields
