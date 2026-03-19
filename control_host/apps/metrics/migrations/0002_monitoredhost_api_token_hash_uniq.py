from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metrics", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="monitoredhost",
            name="api_token_hash",
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
    ]
