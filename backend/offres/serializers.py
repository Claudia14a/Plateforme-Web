from django.contrib.auth import get_user_model
from rest_framework import serializers
from offres.models import OffreStage

User = get_user_model()


def _profil(user):
  # getattr avec valeur par défaut : pas d'erreur si le profil n'existe pas encore
  return getattr(user, 'profil_entreprise', None)


class EntrepriseResumeSerializer(serializers.ModelSerializer):
  """Infos publiques de l'entreprise (sans e-mail ni nom de la personne)."""

  nom = serializers.SerializerMethodField()
  secteur = serializers.SerializerMethodField()
  description = serializers.SerializerMethodField()
  site_web = serializers.SerializerMethodField()
  logo = serializers.SerializerMethodField()

  class Meta:
    model = User
    fields = ('id', 'nom', 'secteur', 'description', 'site_web', 'logo')

  def get_nom(self, obj):
    profil = _profil(obj)
    return profil.nom_entreprise if profil else obj.username

  def get_secteur(self, obj):
    profil = _profil(obj)
    return profil.secteur if profil else None

  def get_description(self, obj):
    profil = _profil(obj)
    return profil.description if profil else None

  def get_site_web(self, obj):
    profil = _profil(obj)
    return profil.site_web if profil else None

  def get_logo(self, obj):
    profil = _profil(obj)
    if not (profil and profil.logo):
      return None
    request = self.context.get('request')
    url = profil.logo.url
    return request.build_absolute_uri(url) if request else url


class OffreStageSerializer(serializers.ModelSerializer):
  # Rempli automatiquement pour une entreprise ; un admin doit le fournir (id du User).
  entreprise = serializers.PrimaryKeyRelatedField(
      queryset=User.objects.filter(role='ENTREPRISE'), required=False
  )
  entreprise_nom = serializers.SerializerMethodField()

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
    read_only_fields = ('id', 'date_creation')

  def get_entreprise_nom(self, obj):
    profil = _profil(obj.entreprise)
    return profil.nom_entreprise if profil else obj.entreprise.username


class OffreStageDetailSerializer(serializers.ModelSerializer):
  entreprise = EntrepriseResumeSerializer(read_only=True)
  entreprise_nom = serializers.SerializerMethodField()

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
    read_only_fields = fields

  def get_entreprise_nom(self, obj):
    profil = _profil(obj.entreprise)
    return profil.nom_entreprise if profil else obj.entreprise.username