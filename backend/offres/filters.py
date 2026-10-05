import django_filters
from django.db.models import Q
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

  # Recherche par mots-clés : chaque mot doit apparaître quelque part dans l'offre
  q = django_filters.CharFilter(method='filtrer_mots_cles')

  class Meta:
    model = OffreStage
    fields = ['domaine', 'ville', 'duree_mois', 'competences_requises', 'active']

  def filtrer_mots_cles(self, queryset, name, value):
    for mot in value.split():
      queryset = queryset.filter(
          Q(titre__icontains=mot)
          | Q(description__icontains=mot)
          | Q(domaine__icontains=mot)
          | Q(ville__icontains=mot)
          | Q(competences_requises__icontains=mot)
      )
    return queryset
