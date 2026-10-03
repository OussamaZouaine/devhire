from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Skill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60)),
                ("slug", models.SlugField(max_length=80, unique=True)),
            ],
            options={"ordering": ["name"], "verbose_name": "Compétence"},
        ),
    ]
