import csv

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils import timezone
from django_filters import rest_framework as filtres
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from administration import audit, stats
from administration.models import AuditLog
from administration.serializers import AuditLogSerializer, UtilisateurAdminSerializer
from candidatures.models import Candidature
from utilisateurs.permissions import IsAdminRole

User = get_user_model()
PERMISSIONS_ADMIN = [permissions.IsAuthenticated, IsAdminRole]


class TableauDeBordView(APIView):
  """GET /api/admin/tableau-de-bord/ : chiffres clés (stages en cours, conventions à traiter...)."""
  permission_classes = PERMISSIONS_ADMIN

  def get(self, request):
    return Response(stats.tableau_de_bord())


class StatistiquesView(APIView):
  """GET /api/admin/statistiques/ : taux d'acceptation, temps moyens, détail par entreprise et par domaine."""
  permission_classes = PERMISSIONS_ADMIN

  def get(self, request):
    return Response(stats.statistiques())


# --- Gestion des utilisateurs ----------------------------------------------

class UtilisateurAdminViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
  """Liste des comptes (?role=, ?is_active=, ?email_verifie=, ?search=) et activation / désactivation."""

  serializer_class = UtilisateurAdminSerializer
  permission_classes = PERMISSIONS_ADMIN
  queryset = User.objects.all().order_by('-date_joined')
  filter_backends = [filtres.DjangoFilterBackend, SearchFilter]
  filterset_fields = ['role', 'is_active', 'email_verifie']
  search_fields = ['username', 'email', 'first_name', 'last_name']

  def _changer_etat(self, request, actif):
    utilisateur = self.get_object()
    if not actif and utilisateur.pk == request.user.pk:
      return Response(
          {'detail': 'Vous ne pouvez pas désactiver votre propre compte.'},
          status=status.HTTP_400_BAD_REQUEST,
      )
    if utilisateur.is_active != actif:
      utilisateur.is_active = actif
      utilisateur.save(update_fields=['is_active'])
      audit.enregistrer(
          request.user, 'UTILISATEUR_ACTIVE' if actif else 'UTILISATEUR_DESACTIVE', utilisateur
      )
    return Response(self.get_serializer(utilisateur).data)

  @action(detail=True, methods=['post'])
  def desactiver(self, request, pk=None):
    """Le compte ne peut plus se connecter et ses tokens cessent immédiatement de fonctionner."""
    return self._changer_etat(request, False)

  @action(detail=True, methods=['post'])
  def activer(self, request, pk=None):
    return self._changer_etat(request, True)


# --- Journal d'audit -------------------------------------------------------

class JournalFiltre(filtres.FilterSet):
  date_min = filtres.DateFilter(field_name='date', lookup_expr='date__gte')
  date_max = filtres.DateFilter(field_name='date', lookup_expr='date__lte')

  class Meta:
    model = AuditLog
    fields = ['action', 'acteur', 'cible_type', 'cible_id']


class JournalPagination(PageNumberPagination):
  page_size = 50
  page_size_query_param = 'page_size'
  max_page_size = 200


class JournalAuditViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
  """Journal d'audit en lecture seule : ?action=, ?acteur=, ?cible_type=, ?date_min=, ?date_max="""
  serializer_class = AuditLogSerializer
  permission_classes = PERMISSIONS_ADMIN
  queryset = AuditLog.objects.select_related('acteur')
  pagination_class = JournalPagination
  filter_backends = [filtres.DjangoFilterBackend]
  filterset_class = JournalFiltre


# --- Rapport CSV -----------------------------------------------------------

def _cellule(valeur):
  """Neutralise l'injection de formules (Excel/LibreOffice) dans les cellules texte."""
  texte = '' if valeur is None else str(valeur)
  return "'" + texte if texte[:1] in ('=', '+', '-', '@', '\t', '\r') else texte


class RapportCandidaturesCSVView(APIView):
  """GET /api/admin/rapports/candidatures.csv : export des candidatures (ouvrable dans Excel)."""
  permission_classes = PERMISSIONS_ADMIN

  def get(self, request):
    reponse = HttpResponse(content_type='text/csv; charset=utf-8')
    reponse['Content-Disposition'] = (
        f'attachment; filename="candidatures_{timezone.localdate():%Y%m%d}.csv"'
    )
    reponse.write('\ufeff')  # BOM : Excel reconnaît l'UTF-8
    ecrivain = csv.writer(reponse, delimiter=';')
    ecrivain.writerow([
        'id', 'date_candidature', 'etudiant', 'offre', 'entreprise', 'domaine', 'ville',
        'statut', 'date_decision', 'delai_traitement_jours', 'convention', 'statut_convention',
    ])
    candidatures = Candidature.objects.select_related(
        'etudiant', 'offre__entreprise__profil_entreprise', 'convention'
    ).order_by('-date_candidature')
    for c in candidatures:
      profil = getattr(c.offre.entreprise, 'profil_entreprise', None)
      convention = getattr(c, 'convention', None)
      delai = (c.date_decision - c.date_candidature).total_seconds() / 86400 if c.date_decision else ''
      ecrivain.writerow([_cellule(v) for v in [
          c.pk, f'{c.date_candidature:%Y-%m-%d %H:%M}', c.etudiant.get_full_name() or c.etudiant.username,
          c.offre.titre, profil.nom_entreprise if profil else c.offre.entreprise.username,
          c.offre.domaine, c.offre.ville, c.get_statut_display(),
          f'{c.date_decision:%Y-%m-%d %H:%M}' if c.date_decision else '',
          round(delai, 2) if delai != '' else '',
          convention.numero if convention else '', convention.get_statut_display() if convention else '',
      ]])
    return reponse
