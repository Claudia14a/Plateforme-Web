from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from utilisateurs.models import ProfilEntreprise, ProfilEtudiant
from utilisateurs.permissions import IsEntrepriseOrAdmin, IsEtudiantOrAdmin
from utilisateurs.serializers import (
    ProfilEntrepriseSerializer,
    ProfilEtudiantSerializer,
    RegisterSerializer,
)


class RegisterView(generics.CreateAPIView):
  """POST /api/utilisateurs/register/ : création d'un compte étudiant ou entreprise."""

  serializer_class = RegisterSerializer
  permission_classes = [permissions.AllowAny]
  authentication_classes = []


class ProfilEtudiantViewSet(viewsets.ModelViewSet):
  queryset = ProfilEtudiant.objects.all()
  serializer_class = ProfilEtudiantSerializer
  permission_classes = [permissions.IsAuthenticated, IsEtudiantOrAdmin]
  parser_classes = (MultiPartParser, FormParser)

  def get_queryset(self):
    user = self.request.user
    if user.is_staff:
      return ProfilEtudiant.objects.select_related('user').order_by('user__username')
    return ProfilEtudiant.objects.select_related('user').filter(user=user).order_by('id')

  def perform_create(self, serializer):
    if ProfilEtudiant.objects.filter(user=self.request.user).exists():
      raise ValidationError('Un profil étudiant existe déjà pour cet utilisateur.')
    serializer.save(utilisateur=self.request.user)


class EntreprisePagination(PageNumberPagination):
  # Permet au front de charger toute la liste des entreprises : ?page_size=100
  page_size_query_param = 'page_size'
  max_page_size = 100


class ProfilEntrepriseViewSet(viewsets.ModelViewSet):
  queryset = ProfilEntreprise.objects.select_related('user').order_by('nom_entreprise')
  serializer_class = ProfilEntrepriseSerializer
  parser_classes = (MultiPartParser, FormParser)
  pagination_class = EntreprisePagination
  filter_backends = [DjangoFilterBackend]
  filterset_fields = ['secteur', 'nom_entreprise']

  def get_permissions(self):
    # Tout utilisateur authentifié peut consulter la liste des entreprises et leurs profils
    if self.action in ['list', 'retrieve']:
      permission_classes = [permissions.IsAuthenticated]
    else:
      permission_classes = [permissions.IsAuthenticated, IsEntrepriseOrAdmin]
    return [permission() for permission in permission_classes]

  def perform_create(self, serializer):
    if ProfilEntreprise.objects.filter(user=self.request.user).exists():
      raise ValidationError('Un profil entreprise existe déjà pour cet utilisateur.')

    serializer.save(user=self.request.user)