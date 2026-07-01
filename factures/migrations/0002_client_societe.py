# Generated manually because the local virtualenv interpreter is not runnable.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('factures', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='societe',
            field=models.CharField(blank=True, max_length=150, verbose_name='Societe'),
        ),
    ]
