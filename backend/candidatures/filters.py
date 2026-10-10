import django_filters

from candidatures.models import Candidature
from offres.filters import filtrer_par_categorie


class CandidatureFilter(django_filters.FilterSet):
  """?statut=EN_ATTENTE&offre=<id>&categorie=<id|slug|id,id,...>
  La catégorie est celle de l'offre visée par la candidature."""

  categorie = django_filters.CharFilter(method='filtrer_categorie')

  class Meta:
    model = Candidature
    fields = ['statut', 'offre', 'categorie']

  def filtrer_categorie(self, queryset, name, value):
    return filtrer_par_categorie(queryset, value, 'offre__categorie')
