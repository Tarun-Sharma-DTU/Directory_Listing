from django.shortcuts import render, redirect
from .tasks import create_company_profile_post
from django.shortcuts import render
import openpyxl
from .models import APIConfig, GeneratedURL
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
import pandas as pd
from django.http import HttpResponse, JsonResponse
from celery.result import AsyncResult
import logging

logger = logging.getLogger(__name__)


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
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        sheet = wb.active
        second_row = sheet[2]
        row_values = [cell.value for cell in second_row]

        api_configs = APIConfig.objects.all()
        GeneratedURL.objects.filter(user=request.user).delete()
        task_ids = []
        delay_seconds = 0  # initial delay

        for api_config in api_configs:
            url = api_config.url.rstrip('/')
            json_url = f"https://{url}/wp-json/wp/v2"
            task = create_company_profile_post.apply_async(
                args=[row_values, json_url, api_config.user, api_config.password, api_config.template_no],
                countdown=delay_seconds
            )
            task_ids.append(task.id)
            delay_seconds += 2  # increment the delay for the next task

        return JsonResponse({'task_ids': task_ids})

    return render(request, "listing/index.html")

@login_required
def get_task_result(request, task_id):
    task_result = AsyncResult(task_id)
    if task_result.ready():
        try:
            url = task_result.result
            if url:
                GeneratedURL.objects.create(user=request.user, url=url)
                logger.info(f"URL saved to database: {url}")
                return JsonResponse({'status': 'SUCCESS', 'url': url})
            else:
                logger.warning("Task returned an empty URL.")
                return JsonResponse({'status': 'FAILURE', 'error': 'Empty URL'})
        except Exception as e:
            logger.error(f"Error saving URL to database: {e}", exc_info=True)
            return JsonResponse({'status': 'ERROR', 'error': str(e)})
    else:
        return JsonResponse({'status': 'PENDING'})

@login_required
def get_generated_links_json(request):
    links = GeneratedURL.objects.filter(user=request.user).order_by('-created_at').values_list('url', flat=True)
    return JsonResponse({'links': list(links)})

@login_required
def get_generated_links(request):
    # Fetch links from the database
    links = GeneratedURL.objects.filter(user=request.user).order_by('-created_at')

    # Create an Excel workbook and sheet
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Generated Links'

    # Adding header
    sheet['A1'] = 'URL'

    # Fill the sheet with URLs
    for row, link in enumerate(links, start=2):  # Start from row 2 to leave the header
        sheet[f'A{row}'] = link.url

    # Prepare response with content type of Excel file
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="generated_links.xlsx"'

    # Save workbook to response
    workbook.save(response)

    return response



def site_data(request):
    if request.method == 'POST':
        excel_file = request.FILES['site_excel_file']

        # Read the Excel file
        df = pd.read_excel(excel_file)

        # Iterate over the rows and update the database
        for index, row in df.iterrows():
            APIConfig.objects.update_or_create(
                url=row['url'],
                defaults={
                    'user': row['user'],
                    'password': row['password'],
                    'template_no': row['template_no']
                }
            )
        
        return HttpResponse("File uploaded and database updated.")
    
    return render(request, "listing/site_data.html")
