import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offres', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Categorie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=150, unique=True)),
                ('slug', models.SlugField(blank=True, max_length=160, unique=True)),
                ('description', models.TextField(blank=True, default='')),
            ],
            options={
                'verbose_name': 'catégorie',
                'verbose_name_plural': 'catégories',
                'ordering': ['nom'],
            },
        ),
        migrations.AddField(
            model_name='offrestage',
            name='categorie',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='offres', to='offres.categorie'),
        ),
    ]
