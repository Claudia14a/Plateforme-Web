from django.http import FileResponse, Http404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from candidatures.models import Candidature
from conventions import services
from conventions.models import Convention
from conventions.serializers import (
    ConventionModificationSerializer,
    ConventionSerializer,
    GenerationSerializer,
    RejetSerializer,
    SignatureSerializer,
)
from utilisateurs.permissions import IsAdminRole, IsEntrepriseOuAdminRole

ACTIONS_ADMIN = {
    'partial_update', 'soumettre', 'rejeter', 'valider', 'signer', 'regenerer', 'generer',
}


def _est_admin(user):
  return user.is_staff or user.role == 'ADMIN'


class ConventionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
  """Conventions de stage.

  Étudiant / entreprise : lecture et téléchargement (jamais les brouillons).
  Administrateur : tout le circuit (modifier, soumettre, valider, rejeter, signer).
  """

  serializer_class = ConventionSerializer
  permission_classes = [permissions.IsAuthenticated]
  parser_classes = [JSONParser, MultiPartParser, FormParser]
  filter_backends = [DjangoFilterBackend]
  filterset_fields = ['statut']

  def get_permissions(self):
    if self.action in ACTIONS_ADMIN:
      return [permissions.IsAuthenticated(), IsAdminRole()]
    if self.action == 'emettre_attestation':
      return [permissions.IsAuthenticated(), IsEntrepriseOuAdminRole()]
    return [permissions.IsAuthenticated()]

  def get_queryset(self):
    user = self.request.user
    qs = Convention.objects.select_related(
        'candidature__offre__entreprise__profil_entreprise', 'candidature__etudiant'
    ).order_by('-date_creation')
    if _est_admin(user):
      return qs
    qs = qs.exclude(statut=Convention.Statut.BROUILLON)
    if user.role == 'ETUDIANT':
      return qs.filter(candidature__etudiant=user)
    if user.role == 'ENTREPRISE':
      return qs.filter(candidature__offre__entreprise=user)
    return qs.none()

  # --- utilitaires ---------------------------------------------------------

  def _reponse(self, convention):
    return Response(self.get_serializer(convention).data)

  def _executer(self, fonction, convention, *args, **kwargs):
    try:
      fonction(convention, *args, **kwargs)
    except services.TransitionInvalide as erreur:
      return Response({'detail': str(erreur)}, status=status.HTTP_409_CONFLICT)
    convention.refresh_from_db()
    return self._reponse(convention)

  @staticmethod
  def _envoyer_fichier(champ, nom):
    if not champ:
      raise Http404
    try:
      flux = champ.open('rb')
    except FileNotFoundError:
      raise Http404
    return FileResponse(flux, as_attachment=True, filename=nom, content_type='application/pdf')

  # --- téléchargements -------------------------------------------------------

  @action(detail=True, methods=['get'], url_path='telecharger')
  def telecharger(self, request, pk=None):
    """PDF de la convention. Étudiant/entreprise : une fois validée ou signée.
    Administrateur : à tout moment (le brouillon porte le filigrane PROJET)."""
    convention = self.get_object()
    if not (_est_admin(request.user) or convention.est_telechargeable):
      return Response(
          {'detail': "La convention n'est pas encore disponible au téléchargement."},
          status=status.HTTP_409_CONFLICT,
      )
    champ = convention.fichier_signe or convention.fichier
    return self._envoyer_fichier(champ, f'convention_{convention.numero or convention.pk}.pdf')

  @action(detail=True, methods=['get'], url_path='attestation')
  def attestation(self, request, pk=None):
    convention = self.get_object()
    return self._envoyer_fichier(
        convention.attestation, f'attestation_{convention.numero or convention.pk}.pdf'
    )

  # --- attestation (entreprise ou admin) -------------------------------------

  @action(detail=True, methods=['post'], url_path='emettre-attestation')
  def emettre_attestation(self, request, pk=None):
    """Délivre l'attestation de stage (convention signée et stage terminé)."""
    return self._executer(services.emettre_attestation, self.get_object(), request.user)

  # --- administration : modification + circuit -------------------------------

  def partial_update(self, request, *args, **kwargs):
    convention = self.get_object()
    serializer = ConventionModificationSerializer(convention, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    return self._executer(services.modifier, convention, serializer.validated_data, request.user)

  @action(detail=True, methods=['post'])
  def soumettre(self, request, pk=None):
    """BROUILLON -> EN_ATTENTE"""
    return self._executer(services.soumettre, self.get_object(), request.user)

  @action(detail=True, methods=['post'])
  def rejeter(self, request, pk=None):
    """EN_ATTENTE -> BROUILLON, avec {"motif": "..."}"""
    donnees = RejetSerializer(data=request.data)
    donnees.is_valid(raise_exception=True)
    return self._executer(
        services.rejeter, self.get_object(), donnees.validated_data['motif'], request.user
    )

  @action(detail=True, methods=['post'])
  def valider(self, request, pk=None):
    """EN_ATTENTE -> VALIDEE (notifie l'étudiant et l'entreprise : « convention prête »)"""
    return self._executer(services.valider, self.get_object(), request.user)

  @action(detail=True, methods=['post'])
  def signer(self, request, pk=None):
    """VALIDEE -> SIGNEE ; champ facultatif `fichier_signe` (scan PDF)"""
    donnees = SignatureSerializer(data=request.data)
    donnees.is_valid(raise_exception=True)
    return self._executer(
        services.signer, self.get_object(), request.user,
        fichier_signe=donnees.validated_data.get('fichier_signe'),
    )

  @action(detail=True, methods=['post'])
  def regenerer(self, request, pk=None):
    """Régénère le PDF depuis les données actuelles (brouillon ou en attente)."""
    convention = self.get_object()
    if not convention.est_modifiable:
      return Response(
          {'detail': "Une convention validée ou signée ne peut plus être régénérée."},
          status=status.HTTP_409_CONFLICT,
      )
    services.regenerer_pdf(convention)
    return self._reponse(convention)

  @action(detail=False, methods=['post'])
  def generer(self, request):
    """Crée la convention d'une candidature acceptée qui n'en a pas encore
    (rattrapage des candidatures acceptées avant la mise en place de la génération automatique)."""
    donnees = GenerationSerializer(data=request.data)
    donnees.is_valid(raise_exception=True)
    try:
      candidature = Candidature.objects.get(pk=donnees.validated_data['candidature'])
    except Candidature.DoesNotExist:
      return Response({'detail': 'Candidature introuvable.'}, status=status.HTTP_404_NOT_FOUND)
    if candidature.statut != Candidature.Statut.ACCEPTEE:
      return Response(
          {'detail': "Seule une candidature acceptée peut avoir une convention."},
          status=status.HTTP_409_CONFLICT,
      )
    convention, creee = services.creer_convention(
        candidature, donnees.validated_data.get('date_debut'), request.user
    )
    return Response(
        self.get_serializer(convention).data,
        status=status.HTTP_201_CREATED if creee else status.HTTP_200_OK,
    )
