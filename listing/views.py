from django.shortcuts import render
from .tasks import create_company_profile_post, sample_task
from django.shortcuts import render
import openpyxl
from .models import APIConfig


def index(request):
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

    # Always render the form page, whether it's a GET or a POST request
    return render(request, "listing/index.html")

def site_data(request):
    return render(request, "listing/site_data.html")
