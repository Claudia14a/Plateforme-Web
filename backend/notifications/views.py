from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from notifications.models import Notification
from notifications.serializers import NotificationSerializer


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
  """Notifications de l'utilisateur connecté.

  - GET  /api/notifications/                 liste (?lue=false pour les non lues, ?type=)
  - GET  /api/notifications/non-lues/        {"count": N} : à interroger toutes les 30-60 s pour le badge
  - POST /api/notifications/<id>/lire/       marquer comme lue
  - POST /api/notifications/tout-lire/       tout marquer comme lu
  - DELETE /api/notifications/<id>/          supprimer
  """

  serializer_class = NotificationSerializer
  permission_classes = [permissions.IsAuthenticated]
  filter_backends = [DjangoFilterBackend]
  filterset_fields = ['lue', 'type']

  def get_queryset(self):
    return Notification.objects.filter(destinataire=self.request.user)

  @action(detail=False, methods=['get'], url_path='non-lues')
  def non_lues(self, request):
    return Response({'count': self.get_queryset().filter(lue=False).count()})

  @action(detail=True, methods=['post'])
  def lire(self, request, pk=None):
    notification = self.get_object()
    if not notification.lue:
      notification.lue = True
      notification.save(update_fields=['lue'])
    return Response(self.get_serializer(notification).data)

  @action(detail=False, methods=['post'], url_path='tout-lire')
  def tout_lire(self, request):
    modifiees = self.get_queryset().filter(lue=False).update(lue=True)
    return Response({'marquees_comme_lues': modifiees})
