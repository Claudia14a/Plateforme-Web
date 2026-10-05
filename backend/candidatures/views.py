import os

from django.http import FileResponse, Http404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from candidatures.models import Candidature
from candidatures.serializers import (
    CandidatureCreateSerializer,
    CandidatureEtudiantSerializer,
    CandidatureRecueSerializer,
    DecisionSerializer,
    EvaluationSerializer,
)
from utilisateurs.permissions import IsEntreprise, IsEtudiant


class _TelechargementMixin:
  """Téléchargement sécurisé du CV et de la lettre : le queryset de la vue limite
  déjà l'accès au propriétaire (étudiant) ou à l'entreprise concernée."""

  def _envoyer_fichier(self, champ):
    candidature = self.get_object()
    fichier = getattr(candidature, champ)
    if not fichier:
      raise Http404
    try:
      flux = fichier.open('rb')
    except FileNotFoundError:
      raise Http404
    nom = f'{champ}_{candidature.etudiant.username}.pdf'
    return FileResponse(
        flux, as_attachment=True, filename=nom, content_type='application/pdf'
    )

  @action(detail=True, methods=['get'], url_path='cv')
  def cv(self, request, pk=None):
    return self._envoyer_fichier('cv')

  @action(detail=True, methods=['get'], url_path='lettre')
  def lettre(self, request, pk=None):
    return self._envoyer_fichier('lettre_motivation')


# --------------------------------------------------------------------------
# Espace étudiant : /api/candidatures/mes-candidatures/
# --------------------------------------------------------------------------

class MesCandidaturesViewSet(
    _TelechargementMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
  """Postuler, suivre ses candidatures (filtre ?statut=), consulter l'historique
  et retirer une candidature encore en attente."""

  permission_classes = [permissions.IsAuthenticated, IsEtudiant]
  parser_classes = (MultiPartParser, FormParser)
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  filterset_fields = ['statut', 'offre']
  ordering_fields = ['date_candidature', 'statut']
  ordering = ['-date_candidature']

  def get_queryset(self):
    return (
        Candidature.objects.filter(etudiant=self.request.user)
        .select_related('offre__entreprise__profil_entreprise', 'convention')
        .order_by('-date_candidature')
    )

  def get_serializer_class(self):
    if self.action == 'create':
      return CandidatureCreateSerializer
    return CandidatureEtudiantSerializer

  def perform_create(self, serializer):
    serializer.save(etudiant=self.request.user)

  def perform_destroy(self, instance):
    if instance.statut != Candidature.Statut.EN_ATTENTE:
      raise ValidationError(
          'Seule une candidature en attente peut être retirée.'
      )
    instance.cv.delete(save=False)
    instance.lettre_motivation.delete(save=False)
    instance.delete()


# --------------------------------------------------------------------------
# Espace entreprise : /api/candidatures/recues/
# --------------------------------------------------------------------------

class CandidaturesRecuesViewSet(
    _TelechargementMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
  """Candidatures reçues sur les offres de l'entreprise connectée.
  Filtres : ?offre=<id>&statut=EN_ATTENTE|ACCEPTEE|REFUSEE"""

  permission_classes = [permissions.IsAuthenticated, IsEntreprise]
  serializer_class = CandidatureRecueSerializer
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  filterset_fields = ['statut', 'offre']
  ordering_fields = ['date_candidature', 'statut']
  ordering = ['-date_candidature']

  def get_queryset(self):
    return (
        Candidature.objects.filter(offre__entreprise=self.request.user)
        .select_related('etudiant__profil_etudiant', 'offre', 'evaluation')
        .order_by('-date_candidature')
    )

  def _decider(self, request, nouveau_statut):
    candidature = self.get_object()
    if candidature.statut != Candidature.Statut.EN_ATTENTE:
      return Response(
          {'detail': 'Cette candidature a déjà été traitée.'},
          status=status.HTTP_409_CONFLICT,
      )
    donnees = DecisionSerializer(data=request.data)
    donnees.is_valid(raise_exception=True)
    candidature.statut = nouveau_statut
    candidature.commentaire_entreprise = donnees.validated_data.get('commentaire', '')
    candidature.date_decision = timezone.now()
    candidature.save(update_fields=['statut', 'commentaire_entreprise', 'date_decision'])
    return Response(self.get_serializer(candidature).data)

  @action(detail=True, methods=['post'])
  def accepter(self, request, pk=None):
    """POST .../recues/<id>/accepter/  {"commentaire": "..."} (facultatif)"""
    return self._decider(request, Candidature.Statut.ACCEPTEE)

  @action(detail=True, methods=['post'])
  def refuser(self, request, pk=None):
    """POST .../recues/<id>/refuser/  {"commentaire": "motif"} (facultatif)"""
    return self._decider(request, Candidature.Statut.REFUSEE)

  @action(detail=True, methods=['get', 'post', 'put', 'patch'], url_path='evaluation')
  def evaluation(self, request, pk=None):
    """Évaluation du stagiaire (uniquement pour une candidature acceptée).
    GET : lire — POST : créer — PUT/PATCH : modifier."""
    candidature = self.get_object()
    existante = getattr(candidature, 'evaluation', None)

    if request.method == 'GET':
      if existante is None:
        return Response({'detail': "Aucune évaluation pour ce stagiaire."}, status=status.HTTP_404_NOT_FOUND)
      return Response(EvaluationSerializer(existante).data)

    if candidature.statut != Candidature.Statut.ACCEPTEE:
      return Response(
          {'detail': "Seul un stagiaire dont la candidature a été acceptée peut être évalué."},
          status=status.HTTP_400_BAD_REQUEST,
      )

    if request.method == 'POST':
      if existante is not None:
        return Response(
            {'detail': "Ce stagiaire est déjà évalué : utilisez PUT ou PATCH pour modifier."},
            status=status.HTTP_400_BAD_REQUEST,
        )
      serializer = EvaluationSerializer(data=request.data)
      serializer.is_valid(raise_exception=True)
      serializer.save(candidature=candidature)
      return Response(serializer.data, status=status.HTTP_201_CREATED)

    if existante is None:
      return Response({'detail': "Aucune évaluation à modifier : utilisez POST."}, status=status.HTTP_404_NOT_FOUND)
    serializer = EvaluationSerializer(
        existante, data=request.data, partial=request.method == 'PATCH'
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)
