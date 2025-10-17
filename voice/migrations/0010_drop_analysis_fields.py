from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("voice", "0009_conversation_satisfaction_indicator_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="conversation",
            name="summary",
        ),
        migrations.RemoveField(
            model_name="conversation",
            name="satisfaction_indicator",
        ),
        migrations.RemoveField(
            model_name="conversation",
            name="structured",
        ),
    ]