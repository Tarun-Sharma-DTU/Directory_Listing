from django.shortcuts import render, redirect
from .tasks import create_company_profile_post, test_post_to_wordpress, delete_from_wordpress, perform_test_task
from django.shortcuts import render
import openpyxl
from .models import APIConfig, GeneratedURL, TestResult, WebsiteData
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
        # File path for the existing Excel file
        existing_file_path = os.path.join(settings.MEDIA_ROOT, 'generated_links.xlsx')

        # Check if the file exists and delete it
        if os.path.exists(existing_file_path):
            os.remove(existing_file_path)

        site_number = int(request.POST.get('site_number'))
        excel_file = request.FILES['excel_file']
        # Read the checkbox for avoiding duplication
        avoid_duplication = 'avoid_duplication' in request.POST
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        sheet = wb.active
        second_row = sheet[2]
        row_values = [cell.value for cell in second_row]
        company_name = row_values[0]  # Assuming the company name is always in the second row's first cell

        api_configs = APIConfig.objects.filter(site_enable=True).order_by('?')
        GeneratedURL.objects.filter(user=request.user).delete()
        task_ids = []
        delay_seconds = 0  # initial delay

        processed_sites_count = 0
        api_configs_iterator = iter(api_configs)

        while processed_sites_count < site_number:
            try:
                api_config = next(api_configs_iterator)
            except StopIteration:
                # No more API configurations to process
                break

            if request.session.get('stop_signal', False):
                break

            # Perform the duplication check only if avoid_duplication is True
            if avoid_duplication:
                website_data = WebsiteData.objects.filter(api_config=api_config).first()
                if website_data:
                    existing_company_names = json.loads(website_data.company_names) if website_data.company_names else []
                    if company_name in existing_company_names:
                        continue  # Skip if company name exists


            # Process the api_config since the company_name doesn't exist in WebsiteData
            website = api_config.website.rstrip('/')
            json_url = f"https://{website}/wp-json/wp/v2"
            task = create_company_profile_post.apply_async(
                args=[row_values, json_url, api_config.website, api_config.user, api_config.password, api_config.template_no],
                countdown=delay_seconds
            )
            task_ids.append(task.id)
            delay_seconds += 2  # Increment the delay for the next task
            processed_sites_count += 1  # Increment the count of processed sites

        return JsonResponse({'task_ids': task_ids})

    return render(request, "listing/index.html")

@login_required
def get_task_result(request, task_id):
    task_result = AsyncResult(task_id)
    if task_result.ready():
        try:
            url, website, company_name = task_result.result
            if url:
                logger.info(f"URL saved to database: {url}")
                GeneratedURL.objects.create(user=request.user, url=url)
                # Retrieve or create WebsiteData for the website
                api_config = APIConfig.objects.get(website=website)
                website_data, created = WebsiteData.objects.get_or_create(api_config=api_config)

                # Safely load company_names as JSON and ensure it's a list
                try:
                    existing_company_names = json.loads(website_data.company_names) if website_data.company_names else []
                except json.JSONDecodeError:
                    existing_company_names = []

                # Add the new company name if it's not already in the list
                if company_name not in existing_company_names:
                    existing_company_names.append(company_name)
                    website_data.company_names = json.dumps(existing_company_names)
                    website_data.save()

                return JsonResponse({'status': 'SUCCESS', 'url': url})
            else:
                logger.warning("Task returned an empty URL.")
                return JsonResponse({'status': 'FAILURE', 'error': 'Empty URL'})
        except Exception as e:
            logger.error(f"Error in get_task_result: {e}", exc_info=True)
            return JsonResponse({'status': 'ERROR', 'error': str(e)})
    else:
        return JsonResponse({'status': 'PENDING'})

@login_required
def get_generated_links_json(request):
    # Fetch links from the database
    links = GeneratedURL.objects.filter(user=request.user).order_by('created_at').values_list('url', flat=True)
    
    # Create an Excel workbook and sheet
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Generated Links'

    # Adding header
    sheet['A1'] = 'URL'

    # Fill the sheet with URLs
    for row, url in enumerate(links, start=2):  # Start from row 2 to leave the header
        sheet[f'A{row}'] = url

    # Define file path
    file_path = os.path.join(settings.MEDIA_ROOT, 'generated_links.xlsx')

    try:
        # Save workbook to the defined file path
        workbook.save(file_path)
        logger.info(f"Excel file successfully saved at {file_path}")
    except Exception as e:
        logger.error(f"Error saving Excel file: {e}", exc_info=True)
        return JsonResponse({'error': 'Failed to create Excel file'})

    # Construct URL to the saved file
    file_url = request.build_absolute_uri(settings.MEDIA_URL + 'generated_links.xlsx')

    # Return JSON response with links and file URL
    return JsonResponse({'links': list(links), 'excel_file_url': file_url})

@login_required
def download_excel(request):
    file_path = os.path.join(settings.MEDIA_ROOT, 'generated_links.xlsx')
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='generated_links.xlsx')


@login_required
def get_django_messages(request):
    messages_list = []
    for message in messages.get_messages(request):
        messages_list.append({
            "level": message.level,
            "message": message.message,
            "tags": message.tags,
        })
    return JsonResponse(messages_list, safe=False)


def site_data(request):
    if request.method == 'POST':
        excel_file = request.FILES['site_excel_file']

        # Read the Excel file
        df = pd.read_excel(excel_file)

        # Iterate over the rows and update the database
        for index, row in df.iterrows():
            APIConfig.objects.update_or_create(
                website=row['url'],
                defaults={
                    'user': row['user'],
                    'password': row['password'],
                    'template_no': row['template_no']
                }
            )
        
        return HttpResponse("File uploaded and database updated.")
    
    return render(request, "listing/site_data.html")


def get_api_config_data(request):
    data = list(APIConfig.objects.values('websites', 'user', 'password', 'template_no'))
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
            task_ids = []
            for config in context['api_configs']:
                perform_test_task.delay(config.id)

            # Store the task_ids in the session for checking completion
            request.session['test_all_task_ids'] = [perform_test_task.delay(config.id).id for config in context['api_configs']]
            
            # Redirect to avoid re-posting on refresh
            return redirect('rest_api_test')

        # If the 'Test Site' button is pressed for a single site
        elif 'test_single' in request.POST:
            selected_url = request.POST.get('api_url')
            try:
                selected_config = APIConfig.objects.get(website=selected_url)
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
    test_all = 'test_all' in request.POST
    # Fetch test results and prepare the context
    test_results = TestResult.objects.all()
    test_status = {result.config.website: result.status for result in test_results}

    if test_all:
        # Save failed URLs to an Excel file
        failed_urls = []

        for url, status in test_status.items():
            if 'Failed' in status:
                failed_urls.append((url, status.split(":")[1].strip()))

        if failed_urls:
            # Create or update the Excel file
            excel_file = 'failed_tests.xlsx'

        if os.path.exists(excel_file):
            existing_data = pd.read_excel(excel_file)
            
            new_failed_urls = []
            for url, status in failed_urls:
                if url not in existing_data['URL'].values:
                    new_failed_urls.append((url, status))

            new_data = pd.DataFrame(new_failed_urls, columns=['URL', 'Status'])
                
            updated_data = pd.concat([existing_data, new_data], ignore_index=True)

            updated_data.to_excel(excel_file, index=False)
        else:
            new_data = pd.DataFrame(failed_urls, columns=['URL', 'Status'])
            new_data.to_excel(excel_file, index=False)

    return JsonResponse(test_status)


def perform_test(request, config):
    try:
        username = config.user
        print(username)
        password = config.password
        response = test_post_to_wordpress(config.website, username, password, "Test Content")
        print(response)        
        test_status = request.session.get('test_status', {})
        if response.status_code in [201]:
            test_status[config.website] = 'Success: Post Created successfully'                
            json_data = response.json()
            post_link = json_data.get('link', None)
            messages.success(request, f"Post Created successfully on {post_link}.")
            
            response_data = json.loads(response.text)
            post_id = response_data.get('id')
            delete_response = delete_from_wordpress(config.website, username, password, post_id)
            
            if delete_response is not None and delete_response.status_code == 200:
                messages.success(request, f"Post deleted successfully on {post_link}.")
            else:
                messages.error(request, "Failed to delete post.")
        else:
            test_status[config.website] = f'Failed: Site test failed with status code: {response.status_code}'
            request.session['test_status'] = test_status
            messages.error(request, f"Site test failed with status code: {response.status_code}")
            # Save the failed URL to an Excel file            
    except Exception as e:
        messages.error(request, f"An error occurred while testing {config.website}: {e}")


def download_file(request):
    file_name = 'failed_tests.xlsx'
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), file_name)
    print(file_path)

    if os.path.exists(file_path):
        # Serve the file directly using FileResponse, which will handle the file opening
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=file_name)
    else:
        return HttpResponseNotFound('The requested file was not found on our server.')
        
        