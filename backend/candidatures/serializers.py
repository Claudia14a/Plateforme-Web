import os

from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from candidatures.models import Candidature, EvaluationStage
from utilisateurs.validators import valider_pdf


def _nom_entreprise(user):
  profil = getattr(user, 'profil_entreprise', None)
  return profil.nom_entreprise if profil else user.username


def _categorie(offre):
  c = offre.categorie
  return {'id': c.id, 'nom': c.nom, 'slug': c.slug} if c else None


# --------------------------------------------------------------------------
# Étudiant
# --------------------------------------------------------------------------

class CandidatureEtudiantSerializer(serializers.ModelSerializer):
  """Vue d'une candidature par l'étudiant (suivi / historique)."""

  route_basename = 'mes-candidatures'

  statut_libelle = serializers.CharField(source='get_statut_display', read_only=True)
  offre = serializers.SerializerMethodField()
  convention = serializers.SerializerMethodField()
  cv_url = serializers.SerializerMethodField()
  lettre_url = serializers.SerializerMethodField()

  class Meta:
    model = Candidature
    fields = (
        'id', 'offre', 'statut', 'statut_libelle', 'message',
        'commentaire_entreprise', 'date_candidature', 'date_decision',
        'cv_url', 'lettre_url', 'convention',
    )
    read_only_fields = fields

  def _url(self, obj, action):
    path = reverse(f'{self.route_basename}-{action}', kwargs={'pk': obj.pk})
    request = self.context.get('request')
    return request.build_absolute_uri(path) if request else path

  def get_cv_url(self, obj):
    return self._url(obj, 'cv')

  def get_lettre_url(self, obj):
    return self._url(obj, 'lettre')

  def get_offre(self, obj):
    o = obj.offre
    return {
        'id': o.id,
        'titre': o.titre,
        'domaine': o.domaine,
        'ville': o.ville,
        'duree_mois': o.duree_mois,
        'date_limite': o.date_limite,
        'active': o.active,
        'entreprise_nom': _nom_entreprise(o.entreprise),
        'categorie': _categorie(o),
    }

  def get_convention(self, obj):
    # Visible seulement une fois la convention sortie du brouillon
    convention = getattr(obj, 'convention', None)
    if convention is None or convention.statut == 'BROUILLON':
      return None
    return {
        'id': convention.id,
        'numero': convention.numero,
        'statut': convention.statut,
        'statut_libelle': convention.get_statut_display(),
        'date_debut': convention.date_debut,
        'date_fin': convention.date_fin,
        'telechargeable': convention.est_telechargeable,
    }


class CandidatureCreateSerializer(serializers.ModelSerializer):
  """Dépôt d'une candidature : lettre de motivation obligatoire, CV facultatif
  (à défaut, le CV du profil est utilisé)."""

  class Meta:
    model = Candidature
    fields = ('id', 'offre', 'cv', 'lettre_motivation', 'message')
    read_only_fields = ('id',)
    extra_kwargs = {'cv': {'required': False}}

  def validate_offre(self, offre):
    if not offre.active or offre.date_limite < timezone.localdate():
      raise serializers.ValidationError("Cette offre n'accepte plus de candidatures.")
    return offre

  def validate_cv(self, fichier):
    return valider_pdf(fichier)

  def validate_lettre_motivation(self, fichier):
    return valider_pdf(fichier)

  def validate(self, attrs):
    etudiant = self.context['request'].user
    if Candidature.objects.filter(etudiant=etudiant, offre=attrs['offre']).exists():
      raise serializers.ValidationError({'offre': 'Vous avez déjà postulé à cette offre.'})
    if not attrs.get('cv'):
      profil = getattr(etudiant, 'profil_etudiant', None)
      if not (profil and profil.cv):
        raise serializers.ValidationError(
            {'cv': 'Joignez un CV (PDF) à votre candidature ou ajoutez-le à votre profil.'}
        )
    return attrs

  def create(self, validated_data):
    # `etudiant` est fourni par la vue : serializer.save(etudiant=request.user)
    if not validated_data.get('cv'):
      profil = validated_data['etudiant'].profil_etudiant
      with profil.cv.open('rb') as f:
        validated_data['cv'] = ContentFile(f.read(), name=os.path.basename(profil.cv.name))
    return super().create(validated_data)

  def to_representation(self, instance):
    return CandidatureEtudiantSerializer(instance, context=self.context).data


# --------------------------------------------------------------------------
# Entreprise
# --------------------------------------------------------------------------

class EvaluationSerializer(serializers.ModelSerializer):
  moyenne = serializers.FloatField(read_only=True)

  class Meta:
    model = EvaluationStage
    fields = (
        'id', 'note_technique', 'note_autonomie', 'note_communication',
        'note_assiduite', 'moyenne', 'appreciation', 'points_forts',
        'axes_amelioration', 'recommande', 'date_evaluation', 'date_modification',
    )
    read_only_fields = ('id', 'moyenne', 'date_evaluation', 'date_modification')


class CandidatureRecueSerializer(CandidatureEtudiantSerializer):
  """Vue d'une candidature par l'entreprise qui a publié l'offre."""

  route_basename = 'candidatures-recues'

  etudiant = serializers.SerializerMethodField()
  evaluation = serializers.SerializerMethodField()

  class Meta:
    model = Candidature
    fields = (
        'id', 'offre', 'etudiant', 'statut', 'statut_libelle', 'message',
        'commentaire_entreprise', 'date_candidature', 'date_decision',
        'cv_url', 'lettre_url', 'convention', 'evaluation',
    )
    read_only_fields = fields

  def get_offre(self, obj):
    return {
        'id': obj.offre_id,
        'titre': obj.offre.titre,
        'categorie': _categorie(obj.offre),
    }

  def get_etudiant(self, obj):
    user = obj.etudiant
    profil = getattr(user, 'profil_etudiant', None)
    return {
        'id': user.id,
        'nom_complet': user.get_full_name() or user.username,
        'email': user.email,
        'telephone': profil.telephone if profil else None,
        'formation': profil.formation if profil else None,
        'niveau_etudes': profil.niveau_etudes if profil else None,
        'competences': profil.competences if profil else None,
    }

  def get_evaluation(self, obj):
    evaluation = getattr(obj, 'evaluation', None)
    if evaluation is None:
      return None
    return {'moyenne': evaluation.moyenne, 'recommande': evaluation.recommande}


class DecisionSerializer(serializers.Serializer):
  """Corps des actions accepter / refuser."""
  commentaire = serializers.CharField(required=False, allow_blank=True, max_length=2000)
  # Facultatif, à l'acceptation : sinon la convention prend automatiquement le
  # premier lundi situé au moins 14 jours plus tard.
  date_debut = serializers.DateField(required=False)

  def validate_date_debut(self, value):
    if value < timezone.localdate():
      raise serializers.ValidationError('La date de début ne peut pas être dans le passé.')
    return value
