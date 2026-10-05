from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .emails import lire_token_verification
from .models import ProfilEntreprise, ProfilEtudiant
from .validators import valider_logo, valider_pdf

User = get_user_model()

ESPACES = ('ETUDIANT', 'ENTREPRISE', 'ADMIN')


class UserSerializer(serializers.ModelSerializer):

  class Meta:
    model = User
    fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'email_verifie')
    read_only_fields = ('role', 'email_verifie')


# --------------------------------------------------------------------------
# Connexion
# --------------------------------------------------------------------------

class LoginSerializer(TokenObtainPairSerializer):
  """Connexion JWT par espace.

  `espace` (optionnel) : ETUDIANT, ENTREPRISE ou ADMIN. Si fourni, le compte doit
  appartenir à cet espace (connexion séparée pour les 3 profils).
  La réponse contient `access`, `refresh` et `user` (dont le rôle).
  """

  espace = serializers.ChoiceField(choices=ESPACES, required=False, write_only=True)

  @classmethod
  def get_token(cls, user):
    token = super().get_token(user)
    token['role'] = user.role
    return token

  def validate(self, attrs):
    espace = attrs.pop('espace', None)
    data = super().validate(attrs)  # identifiants incorrects -> 401
    user = self.user

    if getattr(settings, 'EMAIL_VERIFICATION_REQUIRED', True) and not user.email_verifie:
      raise exceptions.PermissionDenied({
          'detail': "Adresse e-mail non vérifiée. Consultez votre boîte mail.",
          'code': 'email_non_verifie',
      })

    if espace:
      if espace == 'ADMIN':
        autorise = user.is_staff or user.role == 'ADMIN'
      else:
        autorise = user.role == espace
      if not autorise:
        raise exceptions.PermissionDenied({
            'detail': f"Ce compte n'est pas un compte {espace.lower()}.",
            'code': 'mauvais_espace',
        })

    data['user'] = UserSerializer(user).data
    return data


# --------------------------------------------------------------------------
# Inscription, vérification d'e-mail, mot de passe oublié
# --------------------------------------------------------------------------

class RegisterSerializer(serializers.ModelSerializer):
  """Inscription publique : seuls les rôles ETUDIANT et ENTREPRISE sont permis."""

  password = serializers.CharField(write_only=True, style={'input_type': 'password'})
  role = serializers.ChoiceField(
      choices=(('ETUDIANT', 'Étudiant'), ('ENTREPRISE', 'Entreprise')),
      default='ETUDIANT',
  )
  # Obligatoires uniquement si role == ENTREPRISE
  nom_entreprise = serializers.CharField(write_only=True, required=False)
  secteur = serializers.CharField(write_only=True, required=False)

  class Meta:
    model = User
    fields = (
        'id', 'username', 'email', 'password', 'first_name', 'last_name',
        'role', 'nom_entreprise', 'secteur',
    )
    read_only_fields = ('id',)
    extra_kwargs = {'email': {'required': True, 'allow_blank': False}}

  def validate_email(self, value):
    if User.objects.filter(email__iexact=value).exists():
      raise serializers.ValidationError('Cet e-mail est déjà utilisé.')
    return value

  def validate(self, attrs):
    validate_password(attrs['password'], User(username=attrs.get('username', '')))
    if attrs.get('role') == 'ENTREPRISE':
      manquants = {
          champ: 'Ce champ est obligatoire pour une entreprise.'
          for champ in ('nom_entreprise', 'secteur')
          if not attrs.get(champ)
      }
      if manquants:
        raise serializers.ValidationError(manquants)
    return attrs

  @transaction.atomic
  def create(self, validated_data):
    nom_entreprise = validated_data.pop('nom_entreprise', None)
    secteur = validated_data.pop('secteur', None)
    password = validated_data.pop('password')

    user = User.objects.create_user(password=password, email_verifie=False, **validated_data)

    if user.role == 'ENTREPRISE':
      ProfilEntreprise.objects.create(
          user=user, nom_entreprise=nom_entreprise, secteur=secteur
      )
    else:
      ProfilEtudiant.objects.create(user=user)
    return user


class VerifyEmailSerializer(serializers.Serializer):
  token = serializers.CharField()

  def validate(self, attrs):
    try:
      contenu = lire_token_verification(attrs['token'])
    except signing.SignatureExpired:
      raise serializers.ValidationError({'token': 'Ce lien a expiré. Demandez un nouvel e-mail.'})
    except signing.BadSignature:
      raise serializers.ValidationError({'token': 'Lien de vérification invalide.'})
    try:
      user = User.objects.get(pk=contenu['uid'], email=contenu['email'])
    except User.DoesNotExist:
      raise serializers.ValidationError({'token': 'Lien de vérification invalide.'})
    attrs['user'] = user
    return attrs

  def save(self, **kwargs):
    user = self.validated_data['user']
    if not user.email_verifie:
      user.email_verifie = True
      user.save(update_fields=['email_verifie'])
    return user


class EmailSerializer(serializers.Serializer):
  email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
  uid = serializers.CharField()
  token = serializers.CharField()
  password = serializers.CharField(write_only=True, style={'input_type': 'password'})

  def validate(self, attrs):
    erreur = serializers.ValidationError({'token': 'Lien invalide ou expiré.'})
    try:
      user = User.objects.get(pk=force_str(urlsafe_base64_decode(attrs['uid'])))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
      raise erreur
    if not default_token_generator.check_token(user, attrs['token']):
      raise erreur
    try:
      validate_password(attrs['password'], user)
    except Exception as exc:  # DjangoValidationError
      raise serializers.ValidationError({'password': list(getattr(exc, 'messages', [str(exc)]))})
    attrs['user'] = user
    return attrs

  def save(self, **kwargs):
    user = self.validated_data['user']
    user.set_password(self.validated_data['password'])
    user.save(update_fields=['password'])
    return user


# --------------------------------------------------------------------------
# Profils
# --------------------------------------------------------------------------

class _NomsUtilisateurMixin:
  """Met à jour prénom/nom sur le User lié au profil."""

  def _appliquer_noms(self, user, user_data):
    champs = [c for c in ('first_name', 'last_name') if c in user_data]
    for champ in champs:
      setattr(user, champ, user_data[champ])
    if champs:
      user.save(update_fields=champs)


class ProfilEtudiantSerializer(_NomsUtilisateurMixin, serializers.ModelSerializer):
  user = UserSerializer(read_only=True)
  email = serializers.EmailField(source='user.email', read_only=True)
  first_name = serializers.CharField(
      source='user.first_name', required=False, allow_blank=True
  )
  last_name = serializers.CharField(
      source='user.last_name', required=False, allow_blank=True
  )

  class Meta:
    model = ProfilEtudiant
    fields = (
        'id',
        'user',
        'email',
        'first_name',
        'last_name',
        'telephone',
        'formation',
        'niveau_etudes',
        'competences',
        'cv',
        'date_Mise_a_jour',
    )
    read_only_fields = ('id', 'date_Mise_a_jour')

  def validate_cv(self, fichier):
    return valider_pdf(fichier) if fichier else fichier

  def create(self, validated_data):
    # `utilisateur` est fourni par la vue : serializer.save(utilisateur=request.user)
    utilisateur = validated_data.pop('utilisateur')
    user_data = validated_data.pop('user', {})
    profil = ProfilEtudiant.objects.create(user=utilisateur, **validated_data)
    self._appliquer_noms(utilisateur, user_data)
    return profil

  def update(self, instance, validated_data):
    user_data = validated_data.pop('user', {})
    self._appliquer_noms(instance.user, user_data)
    for attr, value in validated_data.items():
      setattr(instance, attr, value)
    instance.save()
    return instance


class ProfilEntrepriseSerializer(serializers.ModelSerializer):
  # `user.id` est la valeur à utiliser pour le champ « entreprise » d'une offre
  user = UserSerializer(read_only=True)

  class Meta:
    model = ProfilEntreprise
    fields = (
        'id',
        'user',
        'nom_entreprise',
        'secteur',
        'description',
        'logo',
        'site_web',
        'telephone',
        'adresse',
        'date_mise_a_jour',
    )
    read_only_fields = ('id', 'date_mise_a_jour')

  def validate_logo(self, fichier):
    return valider_logo(fichier) if fichier else fichier
