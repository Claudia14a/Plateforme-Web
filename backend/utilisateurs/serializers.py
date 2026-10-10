from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
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
from .two_factor import (
    EmailIndisponible,
    LOGIN,
    REGISTER,
    creer_mfa_token,
    deux_facteurs_actif,
    envoyer_code,
    lire_mfa_token,
    masquer_email,
    validite_minutes,
    verifier_code,
)
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
  """Connexion JWT par espace, avec double authentification par e-mail.

  Étape 1 (cette classe) : {username, password, espace?}
    - si TWO_FACTOR_ENABLED (défaut) : un code à 6 chiffres est envoyé par e-mail et la
      réponse contient {requires_2fa: true, mfa_token, email, ...} -- AUCUN jeton JWT.
    - sinon : réponse classique {access, refresh, user}.
  Étape 2 : POST /api/auth/verify-2fa/ {mfa_token, code} -> {access, refresh, user}.

  `espace` (optionnel) : ETUDIANT, ENTREPRISE ou ADMIN. Si fourni, le compte doit
  appartenir à cet espace (connexion séparée pour les 3 profils).
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
    double_facteur = deux_facteurs_actif()

    # Avec la double authentification, le code reçu par e-mail prouve aussi que l'adresse
    # est valide : on ne bloque donc plus ici les comptes « non vérifiés ».
    if (
        not double_facteur
        and getattr(settings, 'EMAIL_VERIFICATION_REQUIRED', True)
        and not user.email_verifie
    ):
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

    if not double_facteur:
      data['user'] = UserSerializer(user).data
      return data

    # --- Double authentification : on n'émet PAS de jetons à cette étape -------------
    if not user.email:
      raise exceptions.PermissionDenied({
          'detail': "Aucune adresse e-mail n'est associée à ce compte : "
                    "impossible d'envoyer le code de connexion.",
          'code': 'email_manquant',
      })
    if not envoyer_code(user, LOGIN):
      raise EmailIndisponible()

    return {
        'requires_2fa': True,
        'mfa_token': creer_mfa_token(user, LOGIN),
        'purpose': LOGIN,
        'email': masquer_email(user.email),
        'expires_in': validite_minutes() * 60,
        'detail': 'Un code de connexion a été envoyé à votre adresse e-mail.',
    }


class Verify2FASerializer(serializers.Serializer):
  """Étape 2 : {mfa_token, code}. Sert à la connexion ET à la confirmation d'inscription."""

  mfa_token = serializers.CharField()
  code = serializers.CharField(max_length=6, min_length=6)

  def validate_code(self, value):
    value = value.strip()
    if not value.isdigit():
      raise serializers.ValidationError('Le code contient 6 chiffres.')
    return value

  def validate(self, attrs):
    user, purpose = lire_mfa_token(attrs['mfa_token'])
    verifier_code(user, purpose, attrs['code'])
    attrs['user'] = user
    attrs['purpose'] = purpose
    return attrs

  def save(self, **kwargs):
    """Finalise : e-mail confirmé (inscription ou première connexion) + date de dernière connexion."""
    user = self.validated_data['user']
    if not user.email_verifie:
      user.email_verifie = True
      user.save(update_fields=['email_verifie'])
    update_last_login(None, user)
    return user

  @staticmethod
  def jetons(user):
    refresh = LoginSerializer.get_token(user)  # contient le claim `role`
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    }


class Renvoyer2FASerializer(serializers.Serializer):
  """{mfa_token} : demande un nouveau code (au plus un par minute)."""

  mfa_token = serializers.CharField()

  def validate(self, attrs):
    attrs['user'], attrs['purpose'] = lire_mfa_token(attrs['mfa_token'])
    return attrs


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
        'profil_public',
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


# --------------------------------------------------------------------------
# Annuaires publics (visiteurs non connectés) : champs strictement limités
# --------------------------------------------------------------------------

class ProfilEntreprisePublicSerializer(serializers.ModelSerializer):
  """Fiche publique d'une entreprise : aucune donnée personnelle du compte (ni e-mail,
  ni identifiant de connexion, ni nom de la personne qui gère le compte)."""

  user = serializers.SerializerMethodField()  # {"id": ...} : valeur du champ « entreprise » d'une offre
  nb_offres_ouvertes = serializers.IntegerField(read_only=True)

  class Meta:
    model = ProfilEntreprise
    fields = (
        'id', 'user', 'nom_entreprise', 'secteur', 'description', 'logo',
        'site_web', 'telephone', 'adresse', 'nb_offres_ouvertes',
    )
    read_only_fields = fields

  def get_user(self, obj):
    return {'id': obj.user_id}


class ProfilEtudiantPublicSerializer(serializers.ModelSerializer):
  """Fiche publique d'un étudiant : prénom + initiale du nom, formation, niveau, compétences.
  Jamais l'e-mail, le téléphone, le CV, l'identifiant de connexion ni le nom complet."""

  nom_affiche = serializers.SerializerMethodField()
  competences_liste = serializers.SerializerMethodField()

  class Meta:
    model = ProfilEtudiant
    fields = (
        'id', 'nom_affiche', 'formation', 'niveau_etudes',
        'competences', 'competences_liste', 'date_Mise_a_jour',
    )
    read_only_fields = fields

  def get_nom_affiche(self, obj):
    prenom = (obj.user.first_name or '').strip()
    nom = (obj.user.last_name or '').strip()
    if prenom and nom:
      return f'{prenom} {nom[0].upper()}.'
    return prenom or 'Étudiant'

  def get_competences_liste(self, obj):
    return [c.strip() for c in (obj.competences or '').split(',') if c.strip()]

