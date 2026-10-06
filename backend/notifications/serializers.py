from rest_framework import serializers
from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
  class Meta:
    model = Notification
    fields = ('id', 'type', 'titre', 'message', 'lien', 'lue', 'date_creation')
    read_only_fields = fields
