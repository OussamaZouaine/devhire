from urllib.parse import urlparse

from django.conf import settings
from django.db import migrations


def configure_site(apps, schema_editor):
    """Password reset emails build links from the Site domain (default: example.com)."""
    Site = apps.get_model("sites", "Site")
    domain = urlparse(settings.SITE_URL).netloc or "127.0.0.1:8000"
    Site.objects.update_or_create(id=settings.SITE_ID, defaults={"domain": domain, "name": "DevHire"})


class Migration(migrations.Migration):
    dependencies = [
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(configure_site, migrations.RunPython.noop),
    ]
