from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.sample_data.loader import load


class Command(BaseCommand):
    help = "Load fictional office data in one transaction; does nothing if already loaded."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password", required=True, help="Password for every fictional demo account."
        )

    def handle(self, *args, password, **options):
        try:
            result = load(password=password)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        if result is None:
            self.stdout.write("Sample data is already loaded; nothing changed.")
            return
        run = result["pay_run"]
        self.stdout.write(self.style.SUCCESS("Loaded fictional sample data."))
        self.stdout.write(f"Accounts: {', '.join(result['users'])}")
        self.stdout.write(f"Locked pay run: {run.year}-{run.month:02d}")
