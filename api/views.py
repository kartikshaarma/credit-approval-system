from django.shortcuts import render

# Create your views here.
import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Customer, Loan
from .serializers import CustomerSerializer, LoanSerializer, LoanDetailSerializer, CustomerLoanSerializer
from django.db.models import Sum
from datetime import date
import math

# Helper function to calculate credit score
def calculate_credit_score(customer_id):
    customer = Customer.objects.get(customer_id=customer_id)
    loans = Loan.objects.filter(customer=customer)

    # i. Past Loans paid on time
    total_emis_paid = sum(loan.emis_paid_on_time for loan in loans)
    total_tenure = sum(loan.tenure for loan in loans)
    paid_on_time_component = (total_emis_paid / total_tenure * 100) if total_tenure > 0 else 100
    
    # ii. No of loans taken in past
    num_loans_taken = loans.count()
    
    # iii. Loan activity in current year
    current_year_loans = loans.filter(start_date__year=date.today().year).count()
    
    # iv. Loan approved volume
    total_loan_volume = sum(loan.loan_amount for loan in loans)

    # v. If sum of current loans > approved limit, credit score = 0
    current_debt = customer.current_debt
    if current_debt > customer.approved_limit:
        return 0

    # A simple weighted scoring model. These weights can be adjusted.
    # We will normalize these values to a score out of 100.
    # For simplicity, we'll use a rule-based approach rather than complex normalization.
    
    credit_score = 0
    
    if paid_on_time_component > 90:
        credit_score += 30
    elif paid_on_time_component > 75:
        credit_score += 15

    if num_loans_taken > 5:
        credit_score += 20
    elif num_loans_taken > 2:
        credit_score += 10
        
    if current_year_loans == 0:
        credit_score += 15
        
    if total_loan_volume < customer.approved_limit * 0.5:
        credit_score += 25
    
    # Cap score at 100
    return min(credit_score, 100)


class RegisterView(APIView):
    def post(self, request):
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        age = request.data.get('age')
        monthly_income = request.data.get('monthly_income')
        phone_number = request.data.get('phone_number')

        # Basic validation
        if not all([first_name, last_name, age, monthly_income, phone_number]):
            return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        approved_limit = round(36 * monthly_income / 100000) * 100000

        customer = Customer.objects.create(
            first_name=first_name,
            last_name=last_name,
            age=age,
            monthly_salary=monthly_income,
            phone_number=phone_number,
            approved_limit=approved_limit
        )
        
        serializer = CustomerSerializer(customer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CheckEligibilityView(APIView):
    def post(self, request):
        customer_id = request.data.get('customer_id')
        loan_amount = request.data.get('loan_amount')
        interest_rate = request.data.get('interest_rate')
        tenure = request.data.get('tenure')

        try:
            customer = Customer.objects.get(customer_id=customer_id)
        except Customer.DoesNotExist:
            return Response({"error": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        credit_score = calculate_credit_score(customer_id)
        
        # Check sum of current EMIs
        current_emis = Loan.objects.filter(customer=customer, end_date__gte=date.today()).aggregate(Sum('monthly_payment'))['monthly_payment__sum'] or 0
        if current_emis > customer.monthly_salary / 2:
            return Response({
                "customer_id": customer_id,
                "approval": False,
                "interest_rate": interest_rate,
                "corrected_interest_rate": interest_rate,
                "tenure": tenure,
                "monthly_installment": 0,
                "message": "Sum of current EMIs exceeds 50% of monthly salary."
            }, status=status.HTTP_200_OK)

        approval = False
        corrected_interest_rate = interest_rate

        if credit_score > 50:
            approval = True
        elif 30 < credit_score <= 50:
            if interest_rate > 12:
                approval = True
            else:
                corrected_interest_rate = 12.0
        elif 10 < credit_score <= 30:
            if interest_rate > 16:
                approval = True
            else:
                corrected_interest_rate = 16.0
        
        if not approval and corrected_interest_rate == interest_rate:
             return Response({
                "customer_id": customer_id,
                "approval": False,
                "interest_rate": interest_rate,
                "corrected_interest_rate": interest_rate,
                "tenure": tenure,
                "monthly_installment": 0,
                "message": f"Loan not approved due to low credit score ({credit_score})."
            }, status=status.HTTP_200_OK)

        # Calculate monthly installment (EMI)
        # Using compound interest formula for EMI: P * r * (1+r)^n / ((1+r)^n - 1)
        monthly_rate = corrected_interest_rate / (12 * 100)
        monthly_installment = (loan_amount * monthly_rate * (1 + monthly_rate)**tenure) / ((1 + monthly_rate)**tenure - 1)

        return Response({
            "customer_id": customer_id,
            "approval": approval,
            "interest_rate": interest_rate,
            "corrected_interest_rate": corrected_interest_rate,
            "tenure": tenure,
            "monthly_installment": round(monthly_installment, 2)
        }, status=status.HTTP_200_OK)


class CreateLoanView(CheckEligibilityView): # Inherits from CheckEligibilityView
    def post(self, request):
        # Run eligibility check first
        eligibility_response = super().post(request)
        
        if not eligibility_response.data.get('approval'):
            return Response({
                "loan_id": None,
                "customer_id": request.data.get('customer_id'),
                "loan_approved": False,
                "message": eligibility_response.data.get("message", "Loan not approved based on eligibility check."),
                "monthly_installment": 0
            }, status=status.HTTP_200_OK)

        # If approved, create the loan
        customer_id = request.data.get('customer_id')
        customer = Customer.objects.get(customer_id=customer_id)
        
        loan = Loan.objects.create(
            customer=customer,
            loan_amount=request.data.get('loan_amount'),
            tenure=request.data.get('tenure'),
            interest_rate=eligibility_response.data.get('corrected_interest_rate'),
            monthly_payment=eligibility_response.data.get('monthly_installment'),
            emis_paid_on_time=0,
            start_date=date.today(),
            end_date=date.today() + pd.DateOffset(months=request.data.get('tenure'))
        )

        return Response({
            "loan_id": loan.loan_id,
            "customer_id": customer_id,
            "loan_approved": True,
            "message": "Loan approved and created successfully.",
            "monthly_installment": loan.monthly_payment
        }, status=status.HTTP_201_CREATED)


class ViewLoanView(APIView):
    def get(self, request, loan_id):
        try:
            loan = Loan.objects.get(loan_id=loan_id)
            serializer = LoanDetailSerializer(loan)
            return Response(serializer.data)
        except Loan.DoesNotExist:
            return Response({"error": "Loan not found."}, status=status.HTTP_404_NOT_FOUND)


class ViewCustomerLoansView(APIView):
    def get(self, request, customer_id):
        try:
            customer = Customer.objects.get(customer_id=customer_id)
            loans = Loan.objects.filter(customer=customer)
            serializer = CustomerLoanSerializer(loans, many=True)
            return Response(serializer.data)
        except Customer.DoesNotExist:
            return Response({"error": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)
