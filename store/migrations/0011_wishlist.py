"""Create Wishlist model"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0010_add_sizestock_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='Wishlist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=models.deletion.CASCADE, to='store.product')),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, to='auth.user')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='wishlist',
            unique_together={('user', 'product')},
        ),
    ]
