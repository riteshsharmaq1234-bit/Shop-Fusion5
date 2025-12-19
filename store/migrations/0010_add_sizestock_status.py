"""Add `status` field to SizeStock and initialize values.

Generated manually to add the missing `status` column so code expecting
`SizeStock.status` will work even when migrations were not auto-generated
after the field was added to the model.
"""

from django.db import migrations, models


def set_status(apps, schema_editor):
    SizeStock = apps.get_model('store', 'SizeStock')
    for ss in SizeStock.objects.all():
        ss.status = 'IN_STOCK' if ss.stock and ss.stock > 0 else 'OUT_OF_STOCK'
        ss.save(update_fields=['status'])


def unset_status(apps, schema_editor):
    # Reverse: set everything to IN_STOCK (safe default)
    SizeStock = apps.get_model('store', 'SizeStock')
    for ss in SizeStock.objects.all():
        ss.status = 'IN_STOCK'
        ss.save(update_fields=['status'])


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0009_cartitem_size_orderitem_size_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sizestock',
            name='status',
            field=models.CharField(default='IN_STOCK', max_length=16),
        ),
        migrations.RunPython(set_status, unset_status),
    ]
