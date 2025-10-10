from django.core.management.base import BaseCommand
from django.utils.timezone import localtime
from voice.models import Conversation

def _truncate(text: str, length: int = 60) -> str:
    if text is None:
        return ""
    text = text.replace("\n", " ").replace("\r", " ")
    return text if len(text) <= length else text[: length - 1] + "…"

class Command(BaseCommand):
    help = "List saved conversations as a table. Shows previews of user, AI and summary."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20, help="Max rows to show (default: 20)")
        parser.add_argument("--order", type=str, choices=["asc", "desc"], default="desc",
                            help="Order by id ascending or descending (default: desc)")

    def handle(self, *args, **opts):
        limit = opts["limit"]
        order = opts["order"]
        qs = Conversation.objects.all().order_by("-id" if order == "desc" else "id")[:limit]

        headers = ["ID", "Created (local)", "Sat", "Label", "User (preview)", "AI (preview)", "Summary (preview)"]
        rows = []
        for c in qs:
            created_local = localtime(c.created_at) if c.created_at else c.created_at
            rows.append([
                str(c.id),
                created_local.strftime("%Y-%m-%d %H:%M:%S") if created_local else "",
                str(c.satisfaction_score) if c.satisfaction_score is not None else "",
                (c.satisfaction_label or ""),
                _truncate(c.user_transcript, 60),
                _truncate(c.ai_transcript, 60),
                _truncate(c.summary, 60),
            ])

        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        def sep(char="-", corner="+"):
            return corner + corner.join(char * (w + 2) for w in widths) + corner

        def fmt_row(vals):
            return "| " + " | ".join(val.ljust(widths[i]) for i, val in enumerate(vals)) + " |"

        self.stdout.write(sep())
        self.stdout.write(fmt_row(headers))
        self.stdout.write(sep("="))
        for r in rows:
            self.stdout.write(fmt_row(r))
        self.stdout.write(sep())
        self.stdout.write(self.style.SUCCESS(f"Total rows shown: {len(rows)}"))