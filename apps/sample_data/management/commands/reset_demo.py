from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.sample_data.loader import load


class Command(BaseCommand):
    help = "Hosted demo only: erase every record and load fresh fictional sample data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password", required=True, help="Password for every fictional demo account."
        )

    def handle(self, *args, password, **options):
        if settings.DEMO_UNTIL is None:
            raise CommandError("reset_demo erases all data; it runs only when DEMO_UNTIL is set.")
        try:
            # One transaction: if loading fails, the previous demo data remains.
            with transaction.atomic():
                if connection.vendor == "postgresql":
                    # TRUNCATE refuses tables with deferred foreign-key checks still pending
                    # from earlier writes in this transaction; run those checks now.
                    with connection.cursor() as cursor:
                        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                call_command("flush", interactive=False, verbosity=0)
                load(password=password)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        self.stdout.write(self.style.SUCCESS("Demo data reset to fresh fictional sample data."))
