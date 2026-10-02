from rest_framework import serializers
from offres.models import OffreStage
from utilisateurs.serializers import (
    UserSerializer,
)  


class OffreStageSerializer(serializers.ModelSerializer):
  entreprise_nom = serializers.CharField(
      source='entreprise.username', read_only=True
  )

  class Meta:
    model = OffreStage
    fields = (
        'id',
        'entreprise',
        'entreprise_nom',
        'titre',
        'description',
        'domaine',
        'ville',
        'duree_mois',
        'competences_requises',
        'date_limite',
        'date_creation',
        'active',
    )
    read_only_fields = ('id', 'entreprise', 'date_creation')
    
class OffreStageDetailSerializer(serializers.ModelSerializer):
  entreprise = UserSerializer(read_only=True)

  class Meta:
    model = OffreStage
    fields = (
        'id',
        'entreprise',
        'titre',
        'description',
        'domaine',
        'ville',
        'duree_mois',
        'competences_requises',
        'date_limite',
        'date_creation',
        'active',
    )
    read_only_fields = ('id', 'entreprise', 'date_creation')