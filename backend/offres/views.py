from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError
from offres.filters import OffreStageFilter
from offres.models import OffreStage
from offres.serializers import OffreStageDetailSerializer, OffreStageSerializer
from utilisateurs.permissions import IsEntrepriseOrAdmin


def _est_admin(user):
  return user.is_staff or user.role == 'ADMIN'


class OffreStageViewSet(viewsets.ModelViewSet):
  serializer_class = OffreStageSerializer
  filter_backends = [DjangoFilterBackend]
  filterset_class = OffreStageFilter

  def get_queryset(self):
    user = self.request.user
    qs = OffreStage.objects.select_related(
        'entreprise__profil_entreprise'
    ).order_by('-date_creation')

    if _est_admin(user):
      return qs
    if self.action in ('list', 'retrieve'):
      # Offres actives pour tous + ses propres offres (même clôturées) pour une entreprise
      return qs.filter(Q(active=True) | Q(entreprise=user))
    # modifier / clôturer / supprimer : uniquement ses propres offres
    return qs.filter(entreprise=user)

  def get_serializer_class(self):
    # Utilise le sérialiseur détaillé pour une seule offre
    if self.action == 'retrieve':
      return OffreStageDetailSerializer
    return OffreStageSerializer

  def get_permissions(self):
    if self.action in ['list', 'retrieve']:
      permission_classes = [permissions.IsAuthenticated]
    else:
      # Seules les entreprises (propriétaires) ou admins peuvent créer/modifier/supprimer
      permission_classes = [permissions.IsAuthenticated, IsEntrepriseOrAdmin]
    return [permission() for permission in permission_classes]

  def perform_create(self, serializer):
    user = self.request.user
    if _est_admin(user):
      if not serializer.validated_data.get('entreprise'):
        raise ValidationError(
            {'entreprise': "Obligatoire : indiquez l'id de l'utilisateur entreprise."}
        )
      serializer.save()
    else:
      serializer.save(entreprise=user)

  def perform_update(self, serializer):
    if _est_admin(self.request.user):
      serializer.save()
    else:
      # Une entreprise ne peut pas transférer son offre à une autre
      serializer.save(entreprise=serializer.instance.entreprise)