from django.shortcuts import render, redirect
from .tasks import create_company_profile_post
from django.shortcuts import render
import openpyxl
from .models import APIConfig
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required



def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            # Redirect to a success page.
            return redirect('home')  # Replace 'home' with the name of your target page
        else:
            # Return an 'invalid login' error message.
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'registration/login.html')  # Replace with your template name

@login_required
def home(request):
    if request.method == 'POST' and 'excel_file' in request.FILES:
        excel_file = request.FILES['excel_file']
        
        # Load the workbook and select the active sheet
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        sheet = wb.active

        # Extract values from the second row cells
        second_row = sheet[2]
        row_values = [cell.value for cell in second_row]

        # Handle other form data
        site_number = request.POST.get('site_number', '')
        html_template = request.POST.get('html_template', '')

        # Dispatch tasks for each API configuration
        api_configs = APIConfig.objects.all()
        for api_config in api_configs:
            url = api_config.url
            user = api_config.user
            password = api_config.password

            print("Dispatching task for URL:", url)
            create_company_profile_post.delay(row_values, url, user, password, html_template)

        # Redirect to the home page (or any other page) to avoid form resubmission
        return redirect('home')  
    # If it's a GET request or any other method, render the form page
    return render(request, "listing/index.html")

def site_data(request):
    return render(request, "listing/site_data.html")
