from django.urls import reverse
from rest_framework import serializers
from conventions.models import Convention
from utilisateurs.validators import valider_pdf


class ConventionSerializer(serializers.ModelSerializer):
  statut_libelle = serializers.CharField(source='get_statut_display', read_only=True)
  offre_titre = serializers.CharField(source='candidature.offre.titre', read_only=True)
  entreprise_nom = serializers.SerializerMethodField()
  etudiant_nom = serializers.SerializerMethodField()
  telechargeable = serializers.BooleanField(source='est_telechargeable', read_only=True)
  modifiable = serializers.BooleanField(source='est_modifiable', read_only=True)
  url_telechargement = serializers.SerializerMethodField()
  attestation_disponible = serializers.SerializerMethodField()
  url_attestation = serializers.SerializerMethodField()

  class Meta:
    model = Convention
    fields = (
        'id', 'numero', 'candidature', 'offre_titre', 'entreprise_nom', 'etudiant_nom',
        'statut', 'statut_libelle', 'sujet', 'missions', 'lieu', 'date_debut', 'date_fin',
        'motif_rejet', 'date_validation', 'date_signature',
        'telechargeable', 'modifiable', 'url_telechargement',
        'attestation_disponible', 'url_attestation',
    )
    read_only_fields = fields

  def _absolu(self, nom_route, obj):
    path = reverse(nom_route, kwargs={'pk': obj.pk})
    request = self.context.get('request')
    return request.build_absolute_uri(path) if request else path

  def get_entreprise_nom(self, obj):
    user = obj.candidature.offre.entreprise
    profil = getattr(user, 'profil_entreprise', None)
    return profil.nom_entreprise if profil else user.username

  def get_etudiant_nom(self, obj):
    user = obj.candidature.etudiant
    return user.get_full_name() or user.username

  def get_url_telechargement(self, obj):
    return self._absolu('convention-telecharger', obj) if obj.est_telechargeable else None

  def get_attestation_disponible(self, obj):
    return bool(obj.attestation)

  def get_url_attestation(self, obj):
    return self._absolu('convention-attestation', obj) if obj.attestation else None


class ConventionModificationSerializer(serializers.ModelSerializer):
  """Champs qu'un administrateur peut corriger avant validation."""

  class Meta:
    model = Convention
    fields = ('sujet', 'missions', 'lieu', 'date_debut', 'date_fin')

  def validate(self, attrs):
    debut = attrs.get('date_debut', getattr(self.instance, 'date_debut', None))
    fin = attrs.get('date_fin', getattr(self.instance, 'date_fin', None))
    if debut and fin and fin <= debut:
      raise serializers.ValidationError({'date_fin': 'La date de fin doit être postérieure à la date de début.'})
    return attrs


class RejetSerializer(serializers.Serializer):
  motif = serializers.CharField(max_length=2000)


class SignatureSerializer(serializers.Serializer):
  fichier_signe = serializers.FileField(required=False)

  def validate_fichier_signe(self, fichier):
    return valider_pdf(fichier)


class GenerationSerializer(serializers.Serializer):
  candidature = serializers.IntegerField()
  date_debut = serializers.DateField(required=False)
