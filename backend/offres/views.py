from django.db.models import Count, ProtectedError, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from offres.filters import OffreStageFilter
from offres.models import Categorie, OffreStage
from offres.serializers import (
    CategorieSerializer,
    OffreStageDetailSerializer,
    OffreStageSerializer,
)
from utilisateurs.authentication import JWTAuthenticationOptionnelle
from utilisateurs.permissions import IsEntreprise, IsEntrepriseOrAdmin

# Actions ouvertes à tous, y compris aux visiteurs non connectés
ACTIONS_PUBLIQUES = ('list', 'retrieve')


class EstAdmin(permissions.BasePermission):
  def has_permission(self, request, view):
    return _est_admin(request.user)


class LecturePubliqueThrottle(AnonRateThrottle):
  """Limite les visiteurs anonymes (anti-aspiration) : 120 requêtes/minute par adresse IP.
  Ne concerne pas les utilisateurs connectés."""
  scope = 'offres_publiques'
  rate = '120/min'


def _est_admin(user):
  return bool(user.is_authenticated and (user.is_staff or getattr(user, 'role', None) == 'ADMIN'))


class OffreStageViewSet(viewsets.ModelViewSet):
  serializer_class = OffreStageSerializer
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  filterset_class = OffreStageFilter
  # Tri : ?ordering=-date_creation | duree_mois | -duree_mois | date_limite
  ordering_fields = ['date_creation', 'duree_mois', 'date_limite']
  ordering = ['-date_creation']

  def get_authenticators(self):
    # Consultation publique : un token absent ou expiré n'empêche pas de voir les offres.
    # Toutes les autres actions gardent l'authentification JWT stricte.
    action = self.action_map.get(self.request.method.lower())
    if action in ACTIONS_PUBLIQUES:
      return [JWTAuthenticationOptionnelle()]
    return super().get_authenticators()

  def get_throttles(self):
    if self.action in ACTIONS_PUBLIQUES:
      return [LecturePubliqueThrottle()]
    return super().get_throttles()

  def get_queryset(self):
    user = self.request.user
    qs = (
        OffreStage.objects.select_related('entreprise__profil_entreprise', 'categorie')
        .annotate(nb_candidatures=Count('candidatures'))
        .order_by('-date_creation')
    )

    if _est_admin(user):
      return qs

    # Offres ouvertes : actives et non expirées (seules visibles par les visiteurs et les étudiants)
    visibles = Q(active=True, date_limite__gte=timezone.localdate())
    if not user.is_authenticated:
      return qs.filter(visibles)
    if self.action in ACTIONS_PUBLIQUES:
      # une entreprise voit en plus toutes ses propres offres (clôturées ou expirées)
      return qs.filter(visibles | Q(entreprise=user))
    # mes-offres / modifier / clôturer / supprimer : uniquement ses propres offres
    return qs.filter(entreprise=user)

  def get_serializer_class(self):
    # Utilise le sérialiseur détaillé pour une seule offre
    if self.action == 'retrieve':
      return OffreStageDetailSerializer
    return OffreStageSerializer

  def get_permissions(self):
    if self.action in ACTIONS_PUBLIQUES:
      permission_classes = [permissions.AllowAny]  # consulter les offres : sans compte
    elif self.action == 'mes_offres':
      permission_classes = [permissions.IsAuthenticated, IsEntreprise]
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

  def destroy(self, request, *args, **kwargs):
    # Une offre qui a reçu des candidatures ne peut pas être supprimée
    # (elle fait partie de l'historique des étudiants) : on la clôture à la place.
    try:
      return super().destroy(request, *args, **kwargs)
    except ProtectedError:
      return Response(
          {'detail': "Cette offre a reçu des candidatures : clôturez-la au lieu de la supprimer."},
          status=status.HTTP_409_CONFLICT,
      )

  @action(detail=False, methods=['get'], url_path='mes-offres')
  def mes_offres(self, request):
    """GET /api/offres/offres/mes-offres/ : toutes mes offres (ouvertes et clôturées)."""
    queryset = self.filter_queryset(self.get_queryset())
    page = self.paginate_queryset(queryset)
    serializer = self.get_serializer(page, many=True)
    return self.get_paginated_response(serializer.data)

  @action(detail=True, methods=['post'])
  def cloturer(self, request, pk=None):
    """POST /api/offres/offres/<id>/cloturer/ : l'offre n'accepte plus de candidatures."""
    offre = self.get_object()
    offre.active = False
    offre.save(update_fields=['active'])
    return Response(self.get_serializer(offre).data)

  @action(detail=True, methods=['post'])
  def reouvrir(self, request, pk=None):
    """POST /api/offres/offres/<id>/reouvrir/ : remet l'offre en ligne."""
    offre = self.get_object()
    offre.active = True
    offre.save(update_fields=['active'])
    return Response(self.get_serializer(offre).data)


class CategorieViewSet(viewsets.ModelViewSet):
  """Catégories d'offres.
  GET /api/offres/categories/ (public, non paginé) : id, nom, slug, nb_offres (offres ouvertes).
  Création / modification / suppression : administrateurs uniquement."""

  serializer_class = CategorieSerializer
  pagination_class = None

  def get_authenticators(self):
    action = self.action_map.get(self.request.method.lower())
    if action in ACTIONS_PUBLIQUES:
      return [JWTAuthenticationOptionnelle()]
    return super().get_authenticators()

  def get_throttles(self):
    if self.action in ACTIONS_PUBLIQUES:
      return [LecturePubliqueThrottle()]
    return super().get_throttles()

  def get_permissions(self):
    if self.action in ACTIONS_PUBLIQUES:
      return [permissions.AllowAny()]
    return [permissions.IsAuthenticated(), EstAdmin()]

  def get_queryset(self):
    ouvertes = Q(offres__active=True, offres__date_limite__gte=timezone.localdate())
    return Categorie.objects.annotate(nb_offres=Count('offres', filter=ouvertes)).order_by('nom')
