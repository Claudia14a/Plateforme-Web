from rest_framework import permissions, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from utilisateurs.models import ProfilEtudiant, ProfilEntreprise
from utilisateurs.permissions import IsEtudiantOrAdmin,IsEntrepriseOrAdmin
from utilisateurs.serializers import ProfilEtudiantSerializer,ProfilEntrepriseSerializer
from django_filters.rest_framework import DjangoFilterBackend



class ProfilEtudiantViewSet(viewsets.ModelViewSet):
  queryset = ProfilEtudiant.objects.all()
  serializer_class = ProfilEtudiantSerializer
  permission_classes = [permissions.IsAuthenticated, IsEtudiantOrAdmin]
  parser_classes = (MultiPartParser, FormParser)

  def get_queryset(self):
    user = self.request.user
    if user.is_staff:
      return ProfilEtudiant.objects.all()
      return ProfilEtudiant.objects.filter(user=user)

  def perform_create(self, serializer):
    serializer.save(user=self.request.user)


class ProfilEntrepriseViewSet(viewsets.ModelViewSet):
  queryset = ProfilEntreprise.objects.all()
  serializer_class = ProfilEntrepriseSerializer
  parser_classes = (MultiPartParser, FormParser)
  filter_backends = [DjangoFilterBackend]
  filterset_fields = ['secteur', 'nom_entreprise']

  def get_permissions(self):
    # Tout utilisateur authentifié peut consulter la liste des entreprises et leurs profils
    if self.action in ['list', 'retrieve']:
      permission_classes = [permissions.IsAuthenticated]
    else:
      # Seule l'entreprise concernée ou un admin peut créer/modifier/supprimer
      permission_classes = [permissions.IsAuthenticated, IsEntrepriseOrAdmin]
    return [permission() for permission in permission_classes]

  def perform_create(self, serializer):
    # Associe automatiquement le profil à l'utilisateur connecté
    serializer.save(user=self.request.user)    

