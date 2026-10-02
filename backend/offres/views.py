from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from offres.filters import OffreStageFilter
from offres.models import OffreStage
from offres.serializers import  OffreStageDetailSerializer, OffreStageSerializer



class OffreStageViewSet(viewsets.ModelViewSet):
  queryset = OffreStage.objects.filter(active=True).order_by('-date_creation')
  serializer_class = OffreStageSerializer
  filter_backends = [DjangoFilterBackend]
  filterset_class = OffreStageFilter

  def get_serializer_class(self):
    # Utilise le sérialiseur détaillé pour une seule offre
    if self.action == 'retrieve':
      return OffreStageDetailSerializer
    return OffreStageSerializer

  def get_permissions(self):
    # Tout le monde 
    if self.action in ['list', 'retrieve']:
      permission_classes = [permissions.IsAuthenticated]
    else:
      # Seules les entreprises ou admins peuvent créer/modifier/supprimer des offres
      permission_classes = [permissions.IsAdminUser]  
    return [permission() for permission in permission_classes]