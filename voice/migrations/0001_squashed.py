# Squashed migration: authoritative schema for the 'voice' app.
# Replaces 0001_initial, 0002_conversation_analysis, 0003_add_raw_response
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    # IMPORTANT:
    # - Keep this file and voice/migrations/__init__.py
    # - Delete older migration files that this squashes.
    # Existing DBs: python manage.py migrate --fake-initial
    replaces = [
        ("voice", "0001_initial"),
        ("voice", "0002_conversation_analysis"),
        ("voice", "0003_add_raw_response"),
    ]

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
            ],
            options={
                "db_table": "voice_conversation",
                "ordering": ["-last_activity", "-id"],
            },
        ),
        migrations.CreateModel(
            name="ConversationAnalysis",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("summary", models.TextField()),
                ("satisfaction_rating", models.IntegerField()),
                ("satisfaction_label", models.CharField(max_length=64)),
                ("user_behavior", models.TextField()),
                ("conversation_topic", models.CharField(max_length=128)),
                ("feedback_summary", models.TextField()),
                ("analysis_timestamp", models.DateTimeField()),
                ("raw_json", models.JSONField(blank=True, null=True)),
                ("raw_response", models.JSONField(blank=True, null=True)),  # included from 0003
                ("created_at", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True, null=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="analyses", to="voice.conversation")),
            ],
            options={
                "db_table": "voice_conversation_analysis",
            },
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(fields=["session_id"], name="voice_conve_session__idx"),
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(fields=["last_activity"], name="voice_conve_last_act_idx"),
        ),
        migrations.AddIndex(
            model_name="conversationanalysis",
            index=models.Index(fields=["conversation"], name="voice_conve_convers_c6f0e2_idx"),
        ),
    ]