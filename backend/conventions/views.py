from django.http import FileResponse, Http404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from conventions.models import Convention
from conventions.serializers import ConventionSerializer


class ConventionViewSet(viewsets.ReadOnlyModelViewSet):
  """Conventions de l'utilisateur connecté (lecture seule).

  - étudiant : les conventions de ses candidatures
  - entreprise : celles de ses offres
  - admin : toutes
  Un brouillon n'est visible ni par l'étudiant ni par l'entreprise.
  """

  serializer_class = ConventionSerializer
  permission_classes = [permissions.IsAuthenticated]

  def get_queryset(self):
    user = self.request.user
    qs = Convention.objects.select_related(
        'candidature__offre__entreprise__profil_entreprise', 'candidature__etudiant'
    ).order_by('-date_creation')
    if user.is_staff or user.role == 'ADMIN':
      return qs
    qs = qs.exclude(statut=Convention.Statut.BROUILLON)
    if user.role == 'ETUDIANT':
      return qs.filter(candidature__etudiant=user)
    if user.role == 'ENTREPRISE':
      return qs.filter(candidature__offre__entreprise=user)
    return qs.none()

  @action(detail=True, methods=['get'], url_path='telecharger')
  def telecharger(self, request, pk=None):
    """GET /api/conventions/<id>/telecharger/ : PDF, une fois validée ou signée."""
    convention = self.get_object()
    if not convention.est_telechargeable:
      return Response(
          {'detail': "La convention n'est pas encore disponible au téléchargement."},
          status=status.HTTP_409_CONFLICT,
      )
    try:
      flux = convention.fichier.open('rb')
    except FileNotFoundError:
      raise Http404
    return FileResponse(
        flux, as_attachment=True, filename=f'convention_stage_{convention.pk}.pdf',
        content_type='application/pdf',
    )
