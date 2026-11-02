from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hotel', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='huesped',
            old_name='rut',
            new_name='documento',
        ),
    ]