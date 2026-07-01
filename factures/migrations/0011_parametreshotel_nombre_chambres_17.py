from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('factures', '0010_parametreshotel_fax_alter_parametreshotel_adresse_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='parametreshotel',
            name='nombre_chambres',
            field=models.PositiveIntegerField(default=17, help_text="Nombre total de chambres (pour statistiques d'occupation)"),
        ),
    ]
