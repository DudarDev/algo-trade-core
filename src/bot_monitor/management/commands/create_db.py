from django.core.management.base import BaseCommand
try:
    from src.shared.db.session import init_db
except ImportError:
    from shared.db.session import init_db

class Command(BaseCommand):
    help = "Initializes database tables for Algo-Trade-Core via SQLAlchemy Base metadata."

    def handle(self, *args, **options):
        self.stdout.write("Initializing database tables...")
        try:
            init_db()
            self.stdout.write(self.style.SUCCESS("Database tables successfully initialized!"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to initialize database: {e}"))
            raise e
