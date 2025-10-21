# Squashed initial migration for 'voice' app: single-table design.
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_activity", models.DateTimeField()),
                ("session_id", models.CharField(blank=True, default="", max_length=128)),
                ("conversation", models.TextField(blank=True, default="")),
                ("summary", models.TextField(blank=True, default="")),
                ("satisfaction_rating", models.IntegerField(blank=True, null=True)),
                ("satisfaction_label", models.CharField(blank=True, default="", max_length=64)),
                ("user_behavior", models.TextField(blank=True, default="")),
                ("conversation_topic", models.CharField(blank=True, default="", max_length=128)),
                ("feedback_summary", models.TextField(blank=True, default="")),
                ("analysis_timestamp", models.DateTimeField(blank=True, null=True)),
                ("raw_json", models.JSONField(blank=True, null=True)),
                ("raw_response", models.JSONField(blank=True, null=True)),
            ],
            options={
                "db_table": "voice_conversation",
                "ordering": ["-last_activity", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(fields=["session_id"], name="voice_conve_session_idx"),
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(fields=["last_activity"], name="voice_conve_last_act_idx"),
        ),
    ]