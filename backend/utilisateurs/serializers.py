from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import ProfilEtudiant

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):

  class Meta:
    model = User
    fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role')
    read_only_fields = ('role',)


class ProfilEtudiantSerializer(serializers.ModelSerializer):
  user = UserSerializer(read_only=True)

class ProfilEntrepriseSerializer(serializers.ModelSerializer):
  user = UserSerializer(read_only=True)
  email = serializers.EmailField(source='user.email', read_only=True)
  username = serializers.CharField(source='user.username', read_only=True)

 
  first_name = serializers.CharField(
      source='user.first_name', required=False, allow_blank=True
  )
  last_name = serializers.CharField(
      source='user.last_name', required=False, allow_blank=True
  )
  email = serializers.EmailField(source='user.email', read_only=True)

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

  def update(self, instance, validated_data):
    user_data = validated_data.pop('user', {})
    user = instance.user

    
    if 'first_name' in user_data:
      user.first_name = user_data['first_name']
    if 'last_name' in user_data:
      user.last_name = user_data['last_name']
    user.save()

    
    for attr, value in validated_data.items():
      setattr(instance, attr, value)
    instance.save()

    return instance