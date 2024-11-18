from django.core.management import BaseCommand

from apps.order.models import PredefinedLocations


class Command(BaseCommand):
    help = 'Creates Predefined Locations'

    def handle(self, *args, **kwargs):
        locations = [
            {'location_name': 'Anor Restaurant', 'location_description': 'The lovely place',
             'latitude': 41.9217425, 'longitude': --87.6651224},
            {'location_name': 'Chayhana Oasis', 'location_description': 'The lovely place',
             'latitude': 25.9293385, 'longitude': -80.1270589},
        ]

        PredefinedLocations.objects.all().delete()
        for location in locations:
            PredefinedLocations.objects.create(**location)
