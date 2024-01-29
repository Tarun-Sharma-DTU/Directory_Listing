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
from django.http import FileResponse, HttpResponseNotFound,Http404
from django.conf import settings
import json
import os
import glob
from urllib.parse import urlparse



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

def get_root_domain(url):
    parsed_url = urlparse(url)
    domain_parts = parsed_url.netloc.split('.')
    root_domain = '.'.join(domain_parts[-2:]) if len(domain_parts) > 1 else parsed_url.netloc
    return root_domain

@login_required
def home(request):
    if request.method == 'POST' and 'excel_file' in request.FILES:
        # Clear the session value
        if 'uploaded_file_name' in request.session:
            del request.session['uploaded_file_name']


        excel_file = request.FILES['excel_file']
        uploaded_file_name = excel_file.name  # Get the uploaded file's name
        request.session['uploaded_file_name'] = uploaded_file_name  # Store the file name in the session

        site_number = int(request.POST.get('site_number'))
        api_configs_count = APIConfig.objects.filter(site_enable=True).count()

        if api_configs_count < site_number:
            return JsonResponse({
                'error': 'Not enough websites to run the requested number of tasks.',
                'api_configs_count': api_configs_count,
            }, status=400)

        wb = openpyxl.load_workbook(excel_file, data_only=True)
        sheet = wb.active
        second_row = sheet[2]
        row_values = [cell.value for cell in second_row]
        company_website = row_values[3]

        api_configs = APIConfig.objects.filter(site_enable=True).order_by('?')
        GeneratedURL.objects.filter(user=request.user).delete()
        task_ids = []
        delay_seconds = 0  # initial delay
        processed_sites_count = 0
        api_configs_iterator = iter(api_configs)

        match_root_domain = 'match_root_domain' in request.POST


        while processed_sites_count < site_number:
            try:
                api_config = next(api_configs_iterator)

                # Handle WebsiteData for duplication check
                website_data, _ = WebsiteData.objects.get_or_create(api_config=api_config)
                
                # Check for existing company websites
                existing_company_websites = json.loads(website_data.company_websites) if website_data.company_websites else []
                # Root domain matching based on checkbox state
                if match_root_domain:
                    new_company_website_root = get_root_domain(company_website)
                    existing_roots = [get_root_domain(url) for url in existing_company_websites]
                    if new_company_website_root in existing_roots:
                        task_ids.append('skipped_task_' + str(processed_sites_count))
                        continue
                else:
                    if company_website in existing_company_websites:
                        task_ids.append('skipped_task_' + str(processed_sites_count))
                        continue
                           
                # Process the api_config since the company_name doesn't exist in WebsiteData
                website = api_config.website.rstrip('/')
                json_url = f"https://{website}/wp-json/wp/v2"
                task = create_company_profile_post.apply_async(
                    args=[row_values, json_url, api_config.website, api_config.user, api_config.password, api_config.template_no],
                    countdown=delay_seconds
                )
                task_ids.append(task.id)
                delay_seconds += 2  # Increment the delay for the next task

            except StopIteration:
                # If no more API configurations to process, add a placeholder task ID
                task_ids.append('placeholder_task_' + str(processed_sites_count))
            
            processed_sites_count += 1  # Increment the count of processed sites

        return JsonResponse({'task_ids': task_ids})   

    return render(request, "listing/index.html")

@login_required
def get_task_result(request, task_id):
    task_result = AsyncResult(task_id)
    if task_result.ready():
        try:
            url, website, company_name, company_website = task_result.result
            if url:
                logger.info(f"URL saved to database: {url}")
                GeneratedURL.objects.create(user=request.user, url=url)

                # Retrieve or create WebsiteData for the website
                api_config = APIConfig.objects.get(website=website)
                website_data, created = WebsiteData.objects.get_or_create(api_config=api_config)

                # Handle company_names
                existing_company_names = json.loads(website_data.company_names) if website_data.company_names else []
                if company_name not in existing_company_names:
                    existing_company_names.append(company_name)
                    website_data.company_names = json.dumps(existing_company_names)

                # Handle company_websites
                existing_company_websites = json.loads(website_data.company_websites) if website_data.company_websites else []
                if company_website not in existing_company_websites and company_website != "":
                    existing_company_websites.append(company_website)
                    website_data.company_websites = json.dumps(existing_company_websites)

                # Save the updated website_data
                website_data.save()

                return JsonResponse({'status': 'SUCCESS', 'url': url})
            else:
                logger.warning("Task returned an empty URL.")
                failure_url = f"{website} - Failed to Post in this Domain" if website else "Task Failed"
                GeneratedURL.objects.create(user=request.user, url=failure_url)
                return JsonResponse({'status': 'FAILURE', 'error': 'Empty URL'})
        except Exception as e:
            logger.error(f"Error in get_task_result in {website}: {e}", exc_info=True)
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

    uploaded_file_name = request.session.get('uploaded_file_name', 'Generated Links')
    if uploaded_file_name:
        # Extract the base file name without the extension
        base_file_name, _ = os.path.splitext(uploaded_file_name)

        # Sanitize the base file name
        sanitized_base_name = ''.join(char for char in base_file_name if char.isalnum() or char in " -_")
        sanitized_base_name = sanitized_base_name[:31]  # Excel sheet title cannot exceed 31 characters
        sheet.title = sanitized_base_name

        # Append '.xlsx' to create the final file name
        file_name = sanitized_base_name + '.xlsx'
    else:
        file_name = 'generated_links.xlsx'

    file_path = os.path.join(settings.MEDIA_ROOT, 'generated_files', file_name)

    # Adding header
    sheet['A1'] = 'URL'

    # Fill the sheet with URLs
    for row, url in enumerate(links, start=2):
        sheet[f'A{row}'] = url

    try:
        # Save workbook to the defined file path
        workbook.save(file_path)
        logger.info(f"Excel file successfully saved at {file_path}")
    except Exception as e:
        logger.error(f"Error saving Excel file: {e}", exc_info=True)
        return JsonResponse({'error': 'Failed to create Excel file'})

    # Construct URL to the saved file
    file_url = request.build_absolute_uri(os.path.join(settings.MEDIA_URL, 'generated_files', file_name))

    # Return JSON response with links and file URL
    return JsonResponse({'links': list(links), 'excel_file_url': file_url})



@login_required
def download_excel(request):
    # Retrieve the filename from the session
    uploaded_file_name = request.session.get('uploaded_file_name')

    # If the file name is not in the session, return an error response
    if not uploaded_file_name:
        return HttpResponseNotFound('No file name found in the session.')

    # Check if the file name already ends with '.xlsx', if not, append it
    if not uploaded_file_name.lower().endswith('.xlsx'):
        uploaded_file_name += '.xlsx'

    # Define the file path
    file_path = os.path.join(settings.MEDIA_ROOT, 'generated_files', uploaded_file_name)

    # Check if the file exists
    if os.path.exists(file_path):
        # Serve the file using a context manager for safe file handling
        with open(file_path, 'rb') as file:
            return FileResponse(file, as_attachment=True, filename=uploaded_file_name)
    else:
        # File not found, return an error response
        return HttpResponseNotFound('The requested file was not found on our server.')


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
        
        # Add a success message
        messages.success(request, "File uploaded and database updated.")
        return redirect('site_data')  # Redirect to the same page

    return render(request, "listing/site_data.html")


def get_api_config_data(request):
    data = list(APIConfig.objects.values('website', 'user', 'password', 'template_no'))
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
    # Fetch test results and prepare the context
    test_results = TestResult.objects.all()
    test_status = {result.config.website: result.status for result in test_results}

    failed_urls = [(url, status.split(":")[1].strip()) for url, status in test_status.items() if 'Failed' in status]

    # Always create an Excel file, but it will be empty if there are no failed URLs
    try:
        excel_file = os.path.join(settings.BASE_DIR, 'failed_tests.xlsx')
        logger.info(f"Creating Excel file at: {excel_file}")

        # Create a DataFrame, it will be empty if failed_urls is empty
        new_data = pd.DataFrame(failed_urls, columns=['URL', 'Status'])
        new_data.to_excel(excel_file, index=False)

        if not failed_urls:
            logger.info("No failed URLs to save, creating an empty Excel file.")

    except Exception as e:
        logger.error(f"Error while creating Excel file: {e}")

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


def download_failed_list(request):
    file_name = 'failed_tests.xlsx'
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), file_name)

    # Check if the file exists
    if not os.path.exists(file_path):
        messages.error(request, "Failed Tests file not found.")
        return HttpResponseNotFound('<h1>File not found</h1>')

    # Open the file without using a context manager
    f = open(file_path, 'rb')
    response = FileResponse(f)
    response['Content-Disposition'] = 'attachment; filename="failed_tests.xlsx"'
    return response


        

def list_files(request):
    media_subdir = os.path.join(settings.MEDIA_ROOT, 'generated_files')
    files = [f for f in os.listdir(media_subdir) if f.endswith('.xlsx')]
    return JsonResponse(files, safe=False)

def download_file(request):
    file_name = request.GET.get('file')  # Get the file name from request
    file_path = os.path.join(settings.MEDIA_ROOT, 'generated_files', file_name)

    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            return response
    raise Http404  # Return 404 if file not found

def delete_all_files(request):
    media_subdir = os.path.join(settings.MEDIA_ROOT, 'generated_files')
    files = glob.glob(os.path.join(media_subdir, '*.xlsx'))
    deleted_files, failed_files = [], []

    for f in files:
        try:
            os.remove(f)
            deleted_files.append(f)
        except Exception as e:
            failed_files.append((f, str(e)))

    if failed_files:
        # Return a response indicating which deletions failed
        return JsonResponse({
            'status': 'partial_success',
            'deleted_files': deleted_files,
            'failed_files': failed_files
        })
    return JsonResponse({'status': 'success', 'deleted_files': deleted_files})
