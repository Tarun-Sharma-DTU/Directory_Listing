from django.shortcuts import render, redirect
from .tasks import create_company_profile_post, test_post_to_wordpress, delete_from_wordpress, perform_test_task
from django.shortcuts import render
import openpyxl
from .models import APIConfig, GeneratedURL, TestResult
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
import pandas as pd
from django.http import HttpResponse, JsonResponse
from celery.result import AsyncResult
import logging
from django.views.decorators.http import require_http_methods
from django.http import FileResponse, HttpResponseNotFound
from django.conf import settings
import json
import os


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
def stop_process(request):
    request.session['stop_signal'] = True
    return JsonResponse({'status': 'stopped'})

@login_required
def home(request):
    if request.method == 'POST' and 'excel_file' in request.FILES:
        site_number = int(request.POST.get('site_number'))
        excel_file = request.FILES['excel_file']
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        sheet = wb.active
        second_row = sheet[2]
        row_values = [cell.value for cell in second_row]

        api_configs = APIConfig.objects.all()
        GeneratedURL.objects.filter(user=request.user).delete()
        task_ids = []
        delay_seconds = 0  # initial delay

        for api_config in api_configs[:site_number+1]:
            if request.session.get('stop_signal', False):
                break
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


def get_api_config_data(request):
    data = list(APIConfig.objects.values('url', 'user', 'password', 'template_no'))
    return JsonResponse(data, safe=False)


@require_http_methods(["GET", "POST"])
def rest_api_test(request):
    context = {'api_configs': APIConfig.objects.all()}

    # Clear previous results when the page is freshly loaded (GET request)
    if request.method == 'GET':
        TestResult.objects.all().delete()
        request.session['test_status'] = {}  # Also clear the session info if you are using it

    if request.method == 'POST':
        # If the 'Test All' button is pressed
        if 'test_all' in request.POST:
            for config in context['api_configs']:
                perform_test_task.delay(config.id)
        # If the 'Test Site' button is pressed for a single site
        elif 'test_single' in request.POST:
            selected_url = request.POST.get('api_url')
            try:
                selected_config = APIConfig.objects.get(url=selected_url)
                perform_test_task.delay(selected_config.id)
            except APIConfig.DoesNotExist:
                messages.error(request, "Selected site configuration does not exist.")
            except APIConfig.MultipleObjectsReturned:
                messages.error(request, "Multiple configurations found for the selected site.")
            except Exception as e:
                messages.error(request, f"An error occurred on {selected_url}: {e}")

        # Redirect to avoid re-posting on refresh
        return redirect('rest_api_test')

    # Render the page with context
    return render(request, 'listing/rest_api_test.html', context)

def test_status_update(request):
    # Fetch test results and prepare the context
    test_results = TestResult.objects.all()
    test_status = {result.config.url: result.status for result in test_results}
    return JsonResponse(test_status)

def perform_test(request, config):
    try:
        username = config.user
        print(username)
        password = config.password
        response = test_post_to_wordpress(config.url, username, password, "Test Content")
        print(response)        
        test_status = request.session.get('test_status', {})
        if response.status_code in [201]:
            test_status[config.url] = 'Success: Post Created successfully'                
            json_data = response.json()
            post_link = json_data.get('link', None)
            messages.success(request, f"Post Created successfully on {post_link}.")
            
            response_data = json.loads(response.text)
            post_id = response_data.get('id')
            delete_response = delete_from_wordpress(config.url, username, password, post_id)
            
            if delete_response is not None and delete_response.status_code == 200:
                messages.success(request, f"Post deleted successfully on {post_link}.")
            else:
                messages.error(request, "Failed to delete post.")
        else:
            test_status[config.url] = f'Failed: Site test failed with status code: {response.status_code}'
            request.session['test_status'] = test_status
            messages.error(request, f"Site test failed with status code: {response.status_code}")
            # Save the failed URL to an Excel file
            failed_url = {'URL': [config.url], 'Status Code': [response.status_code]}
            new_df = pd.DataFrame(failed_url)
            excel_file = 'failed_tests.xlsx'
            if os.path.exists(excel_file):
                # Read existing data
                existing_data = pd.read_excel(excel_file)
                # Concatenate new data with existing data
                updated_data = pd.concat([existing_data, new_df], ignore_index=True)
                updated_data.to_excel(excel_file, index=False)
            else:
                # If file does not exist, create new file
                new_df.to_excel(excel_file, index=False)
    except Exception as e:
        messages.error(request, f"An error occurred while testing {config.url}: {e}")


def download_file(request):
    file_name = 'failed_tests.xlsx'
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), file_name)
    print(file_path)

    if os.path.exists(file_path):
        # Serve the file directly using FileResponse, which will handle the file opening
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=file_name)
    else:
        return HttpResponseNotFound('The requested file was not found on our server.')
        
        