from django.db import migrations


class Migration(migrations.Migration):
    """
    No-op migration: user_name is already created in 0001_initial.
    Keeping this file as a placeholder prevents duplicate column errors.
    """

    dependencies = [
        ("voice", "0001_initial"),
    ]

    operations = [
        # Intentionally empty; 0001 already contains user_name.
    ]