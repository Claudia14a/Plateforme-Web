from rest_framework import serializers

TAILLE_MAX_PDF = 5 * 1024 * 1024   # 5 Mo
TAILLE_MAX_LOGO = 2 * 1024 * 1024  # 2 Mo


def valider_pdf(fichier, taille_max=TAILLE_MAX_PDF):
  """Accepte uniquement un vrai PDF (extension + signature) de taille raisonnable."""
  nom = (getattr(fichier, 'name', '') or '').lower()
  if not nom.endswith('.pdf'):
    raise serializers.ValidationError('Le fichier doit être au format PDF.')
  if fichier.size > taille_max:
    raise serializers.ValidationError(
        f'Le fichier ne doit pas dépasser {taille_max // (1024 * 1024)} Mo.'
    )
  debut = fichier.read(5)
  fichier.seek(0)
  if debut != b'%PDF-':
    raise serializers.ValidationError("Le contenu du fichier n'est pas un PDF valide.")
  return fichier


def valider_logo(fichier):
  if fichier.size > TAILLE_MAX_LOGO:
    raise serializers.ValidationError('Le logo ne doit pas dépasser 2 Mo.')
  return fichier
