from django.core.management.base import BaseCommand
from store.models import SizeStock
from django.conf import settings

class Command(BaseCommand):
    help = 'Restock size-level SKUs that are out of stock to configured defaults'

    def handle(self, *args, **options):
        restocked = 0
        for ss in SizeStock.objects.filter(stock__lte=0):
            # Determine restock target: prefer global setting, else product-based default
            target = getattr(settings, 'RESTOCK_SIZE_QUANTITY', None)
            if target is None:
                try:
                    target = ss.product.initial_total_stock // 5
                except Exception:
                    target = 2
            if not target or target <= 0:
                target = 2
            if ss.restock_to(target):
                restocked += 1
        self.stdout.write(self.style.SUCCESS(f'Restocked {restocked} sizes'))
