from django.urls import reverse
from rest_framework import serializers
from conventions.models import Convention


class ConventionSerializer(serializers.ModelSerializer):
  statut_libelle = serializers.CharField(source='get_statut_display', read_only=True)
  offre_titre = serializers.CharField(source='candidature.offre.titre', read_only=True)
  entreprise_nom = serializers.SerializerMethodField()
  etudiant_nom = serializers.SerializerMethodField()
  telechargeable = serializers.BooleanField(source='est_telechargeable', read_only=True)
  url_telechargement = serializers.SerializerMethodField()

  class Meta:
    model = Convention
    fields = (
        'id', 'candidature', 'offre_titre', 'entreprise_nom', 'etudiant_nom',
        'statut', 'statut_libelle', 'date_debut', 'date_fin',
        'telechargeable', 'url_telechargement',
    )
    read_only_fields = fields

  def get_entreprise_nom(self, obj):
    user = obj.candidature.offre.entreprise
    profil = getattr(user, 'profil_entreprise', None)
    return profil.nom_entreprise if profil else user.username

  def get_etudiant_nom(self, obj):
    user = obj.candidature.etudiant
    return user.get_full_name() or user.username

  def get_url_telechargement(self, obj):
    if not obj.est_telechargeable:
      return None
    path = reverse('convention-telecharger', kwargs={'pk': obj.pk})
    request = self.context.get('request')
    return request.build_absolute_uri(path) if request else path
