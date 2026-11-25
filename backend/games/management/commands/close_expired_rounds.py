import time
from django.core.management.base import BaseCommand
from django.utils import timezone

from games.models import RoundQuestion
from games.services import evaluate_round


class Command(BaseCommand):
    help = "Closes active questions and rounds whose deadlines have expired."

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Run check periodically in a loop until stopped with Ctrl+C.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="Interval in seconds between checks in loop mode.",
        )

    def handle(self, *args, **options):
        is_loop = options.get("loop", False)
        interval = options.get("interval", 5)

        if not is_loop:
            self.close_expired()
        else:
            self.stdout.write(f"Starting loop with interval {interval}s. Press Ctrl+C to stop.")
            try:
                while True:
                    self.close_expired()
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write("\nLoop stopped cleanly.")

    def close_expired(self):
        now = timezone.now()
        expired_qs = RoundQuestion.objects.filter(
            status=RoundQuestion.ACTIVE,
            deadline__lte=now,
        ).select_related("round")

        processed = 0
        skipped = 0

        for q in expired_qs:
            try:
                res = evaluate_round(q.round, timestamp=now)
                if res is not None:
                    processed += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1

        self.stdout.write(f"Processed: {processed}, Skipped: {skipped}")
