from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from offres.models import Categorie, OffreStage

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


class CategorieSerializer(serializers.ModelSerializer):
  # Nombre d'offres ouvertes dans la catégorie (calculé par la vue)
  nb_offres = serializers.IntegerField(read_only=True)

  class Meta:
    model = Categorie
    fields = ('id', 'nom', 'slug', 'description', 'nb_offres')
    read_only_fields = ('id', 'slug', 'nb_offres')


class CategorieResumeSerializer(serializers.ModelSerializer):
  class Meta:
    model = Categorie
    fields = ('id', 'nom', 'slug')
    read_only_fields = fields


class OffreStageSerializer(serializers.ModelSerializer):
  # Rempli automatiquement pour une entreprise ; un admin doit le fournir (id du User).
  entreprise = serializers.PrimaryKeyRelatedField(
      queryset=User.objects.filter(role='ENTREPRISE'), required=False
  )
  entreprise_nom = serializers.SerializerMethodField()
  # Catégorie : id en écriture (obligatoire à la création), nom en lecture
  categorie = serializers.PrimaryKeyRelatedField(
      queryset=Categorie.objects.all(), required=False, allow_null=True
  )
  categorie_nom = serializers.CharField(source='categorie.nom', read_only=True, default=None)
  # Nombre de candidatures reçues (calculé par la vue ; absent juste après une création)
  nb_candidatures = serializers.IntegerField(read_only=True)

  class Meta:
    model = OffreStage
    fields = (
        'id',
        'entreprise',
        'entreprise_nom',
        'categorie',
        'categorie_nom',
        'titre',
        'description',
        'domaine',
        'ville',
        'duree_mois',
        'competences_requises',
        'date_limite',
        'date_creation',
        'active',
        'nb_candidatures',
    )
    read_only_fields = ('id', 'date_creation')

  def get_entreprise_nom(self, obj):
    profil = _profil(obj.entreprise)
    return profil.nom_entreprise if profil else obj.entreprise.username

  def validate_date_limite(self, value):
    # À la création, la date limite ne peut pas être déjà passée
    if self.instance is None and value < timezone.localdate():
      raise serializers.ValidationError('La date limite ne peut pas être dans le passé.')
    return value

  def validate_duree_mois(self, value):
    if value < 1:
      raise serializers.ValidationError('La durée doit être d\'au moins 1 mois.')
    return value

  def validate(self, attrs):
    # À la création, la catégorie est obligatoire (les anciennes offres peuvent en être dépourvues)
    if self.instance is None and not attrs.get('categorie'):
      raise serializers.ValidationError({'categorie': 'Choisissez une catégorie.'})
    return attrs


class OffreStageDetailSerializer(serializers.ModelSerializer):
  entreprise = EntrepriseResumeSerializer(read_only=True)
  entreprise_nom = serializers.SerializerMethodField()
  categorie = CategorieResumeSerializer(read_only=True)
  nb_candidatures = serializers.IntegerField(read_only=True)

  class Meta:
    model = OffreStage
    fields = (
        'id',
        'entreprise',
        'entreprise_nom',
        'categorie',
        'titre',
        'description',
        'domaine',
        'ville',
        'duree_mois',
        'competences_requises',
        'date_limite',
        'date_creation',
        'active',
        'nb_candidatures',
    )
    read_only_fields = fields

  def get_entreprise_nom(self, obj):
    profil = _profil(obj.entreprise)
    return profil.nom_entreprise if profil else obj.entreprise.username
