# api/management/commands/ingest_data.py

from django.core.management.base import BaseCommand
from api.tasks import ingest_data # Import the new combined task

class Command(BaseCommand):
    help = 'Ingests customer and loan data from Excel files into the database using a background task.'

    def handle(self, *args, **options):
        customer_file_path = 'data/customer_data.xlsx'
        loan_file_path = 'data/loan_data.xlsx'

        self.stdout.write(self.style.NOTICE('Starting data ingestion process...'))
        
        # Start the combined data ingestion task
        task = ingest_data.delay(customer_file_path, loan_file_path)
        
        self.stdout.write(self.style.SUCCESS(f'Data ingestion task sent to Celery. Task ID: {task.id}'))
        self.stdout.write(self.style.NOTICE('Check Celery worker logs for progress.'))