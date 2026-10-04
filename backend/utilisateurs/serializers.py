from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from .models import ProfilEntreprise, ProfilEtudiant

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):

  class Meta:
    model = User
    fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role')
    read_only_fields = ('role',)


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

  def validate_email(self, value):
    if value and User.objects.filter(email__iexact=value).exists():
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

    user = User.objects.create_user(password=password, **validated_data)

    if user.role == 'ENTREPRISE':
      ProfilEntreprise.objects.create(
          user=user, nom_entreprise=nom_entreprise, secteur=secteur
      )
    else:
      ProfilEtudiant.objects.create(user=user)
    return user