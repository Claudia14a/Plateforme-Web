from django.db import migrations
from django.utils.text import slugify


def creer_categories(apps, schema_editor):
  """Reprise de l'existant : chaque domaine déjà saisi devient une catégorie
  et les offres correspondantes y sont rattachées."""
  Categorie = apps.get_model('offres', 'Categorie')
  OffreStage = apps.get_model('offres', 'OffreStage')

  par_cle = {}  # clé insensible à la casse -> Categorie
  for categorie in Categorie.objects.all():
    par_cle[categorie.nom.lower()] = categorie
  slugs = set(Categorie.objects.values_list('slug', flat=True))

  for offre in OffreStage.objects.filter(categorie__isnull=True):
    nom = ' '.join((offre.domaine or '').split())
    if not nom:
      continue
    categorie = par_cle.get(nom.lower())
    if categorie is None:
      base = slugify(nom) or 'categorie'
      slug, n = base, 2
      while slug in slugs:
        slug = f'{base}-{n}'
        n += 1
      slugs.add(slug)
      categorie = Categorie.objects.create(nom=nom, slug=slug)
      par_cle[nom.lower()] = categorie
    offre.categorie = categorie
    offre.save(update_fields=['categorie'])


class Migration(migrations.Migration):

    dependencies = [
        ('offres', '0002_categorie'),
    ]

    operations = [
        migrations.RunPython(creer_categories, migrations.RunPython.noop),
    ]
