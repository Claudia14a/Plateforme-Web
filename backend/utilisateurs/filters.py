import django_filters
from django.db.models import Q

from utilisateurs.models import ProfilEntreprise, ProfilEtudiant


def _mots_cles(queryset, value, champs):
  """Chaque mot saisi doit apparaître dans au moins un des champs listés."""
  for mot in value.split():
    condition = Q()
    for champ in champs:
      condition |= Q(**{f'{champ}__icontains': mot})
    queryset = queryset.filter(condition)
  return queryset


class ProfilEntrepriseFilter(django_filters.FilterSet):
  secteur = django_filters.CharFilter(lookup_expr='icontains')
  nom_entreprise = django_filters.CharFilter(lookup_expr='icontains')
  q = django_filters.CharFilter(method='filtrer_mots_cles')

  class Meta:
    model = ProfilEntreprise
    fields = ['secteur', 'nom_entreprise']

  def filtrer_mots_cles(self, queryset, name, value):
    return _mots_cles(queryset, value, ['nom_entreprise', 'secteur', 'description'])


class EtudiantPublicFilter(django_filters.FilterSet):
  """Filtres de l'annuaire public : uniquement sur des champs eux-mêmes publics
  (jamais sur l'e-mail, le téléphone ou le nom de famille, pour ne pas les deviner par recherche)."""

  formation = django_filters.CharFilter(lookup_expr='icontains')
  niveau_etudes = django_filters.CharFilter(lookup_expr='icontains')
  competences = django_filters.CharFilter(lookup_expr='icontains')
  q = django_filters.CharFilter(method='filtrer_mots_cles')

  class Meta:
    model = ProfilEtudiant
    fields = ['formation', 'niveau_etudes', 'competences']

  def filtrer_mots_cles(self, queryset, name, value):
    return _mots_cles(queryset, value, ['formation', 'niveau_etudes', 'competences', 'user__first_name'])
