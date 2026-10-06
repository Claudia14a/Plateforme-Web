from django.core.management.base import BaseCommand

from candidatures.models import Candidature
from conventions.services import creer_convention


class Command(BaseCommand):
  help = ("Crée (et génère le PDF de) la convention de chaque candidature acceptée qui n'en a pas. "
          "Utile une seule fois, pour les candidatures acceptées avant la génération automatique.")

  def handle(self, *args, **options):
    total = 0
    for candidature in Candidature.objects.filter(
        statut=Candidature.Statut.ACCEPTEE, convention__isnull=True
    ).select_related('offre__entreprise', 'etudiant'):
      convention, creee = creer_convention(candidature)
      total += int(creee)
      self.stdout.write(f'  {convention.numero} : {candidature}')
    self.stdout.write(self.style.SUCCESS(f'{total} convention(s) créée(s).'))
