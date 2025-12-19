from store.models import Product, SizeStock
p = Product.objects.first()
print('Product:', p)
ss = SizeStock.objects.filter(product=p, size='L').first()
print('pre L stock:', ss.stock if ss else None)
# simulate adding L size with +2 stock
ss2, created = SizeStock.objects.get_or_create(product=p, size='L', defaults={'stock': 2, 'status': SizeStock.STATUS_IN if 2>0 else SizeStock.STATUS_OUT})
if not created:
    ss2.stock = ss2.stock + 2
    ss2.mark_status()
    ss2.save(update_fields=['stock','status'])
print('post L stock:', SizeStock.objects.get(product=p, size='L').stock)