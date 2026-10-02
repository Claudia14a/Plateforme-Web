import django_filters
from .models import OffreStage


class OffreStageFilter(django_filters.FilterSet):
  # Filtre insensible à la casse pour le domaine et la ville
  domaine = django_filters.CharFilter(
      lookup_expr='icontains'
  )
  ville = django_filters.CharFilter(lookup_expr='icontains')

  # Filtre pour les compétences (recherche partielle sur les compétences requises)
  competences_requises = django_filters.CharFilter(lookup_expr='icontains')

  # Filtres pour la durée 
  duree_mois = django_filters.NumberFilter()
  duree_max = django_filters.NumberFilter(
      field_name='duree_mois', lookup_expr='lte'
  )
  duree_min = django_filters.NumberFilter(
      field_name='duree_mois', lookup_expr='gte'
  )

  class Meta:
    model = OffreStage
    fields = ['domaine', 'ville', 'duree_mois', 'competences_requises', 'active']