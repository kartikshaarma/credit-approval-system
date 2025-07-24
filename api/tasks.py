# api/tasks.py

import pandas as pd
from celery import shared_task
from .models import Customer, Loan
from django.db import transaction
import math
from datetime import date

@shared_task
def ingest_data(customer_file_path, loan_file_path):
    """
    Celery task to read customer and loan data and save it to the database.
    This task is now combined and idempotent.
    """
    try:
        # --- Ingest Customers ---
        customer_df = pd.read_excel(customer_file_path)
        for _, row in customer_df.iterrows():
            # Use update_or_create to prevent duplicate entries
            Customer.objects.update_or_create(
                customer_id=row['Customer ID'],
                defaults={
                    'first_name': row['First Name'],
                    'last_name': row['Last Name'],
                    'age': row['Age'],
                    'phone_number': row['Phone Number'],
                    'monthly_salary': row['Monthly Salary'],
                    'approved_limit': row['Approved Limit'],
                }
            )
        
        # --- Ingest Loans ---
        loan_df = pd.read_excel(loan_file_path)
        all_customer_ids = set(Customer.objects.values_list('customer_id', flat=True))

        for _, row in loan_df.iterrows():
            customer_id = row['Customer ID']
            loan_id = row['Loan ID']

            # Only proceed if the customer exists and the loan doesn't
            if customer_id in all_customer_ids and not Loan.objects.filter(loan_id=loan_id).exists():
                customer_instance = Customer.objects.get(customer_id=customer_id)
                Loan.objects.create(
                    customer=customer_instance,
                    loan_id=loan_id,
                    loan_amount=row['Loan Amount'],
                    tenure=row['Tenure'],
                    interest_rate=row['Interest Rate'],
                    monthly_payment=row['Monthly payment'],
                    emis_paid_on_time=row['EMIs paid on Time'],
                    start_date=row['Date of Approval'],
                    end_date=row['End Date']
                )

        # --- Calculate Current Debt ---
        # Use a transaction to ensure data integrity
        with transaction.atomic():
            for customer in Customer.objects.all():
                # Find loans that are currently active
                current_loans = Loan.objects.filter(customer=customer, end_date__gte=date.today())
                
                # Calculate remaining principal for each loan
                total_debt = 0
                for loan in current_loans:
                    # A simple approximation of remaining debt
                    # For a more accurate calculation, an amortization schedule would be needed.
                    # This logic assumes linear repayment for simplicity.
                    total_emis = loan.tenure
                    paid_emis = loan.emis_paid_on_time
                    if total_emis > 0:
                        remaining_principal = (loan.loan_amount * (total_emis - paid_emis)) / total_emis
                        total_debt += remaining_principal
                
                customer.current_debt = round(total_debt, 2)
                customer.save()

        return "Successfully ingested all data and updated current debts."

    except Exception as e:
        # Log the full error for debugging
        import traceback
        traceback.print_exc()
        return f"An error occurred: {str(e)}"