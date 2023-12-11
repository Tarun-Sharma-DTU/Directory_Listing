from celery import shared_task
import requests
import base64


@shared_task
def sample_task():
  print("Test task executed.")
  return 1

@shared_task
def create_company_profile_post(row_values, url, user, password, template):
    credentials = user + ':' + password
    token = base64.b64encode(credentials.encode())
    header = {'Authorization': 'Basic ' + token.decode('utf-8')}
    # Ensure row_values is a list with enough elements

    company_name = row_values[0]
    description = row_values[1]
    complete_address = row_values[2]
    company_website = row_values[3]
    company_phone_number = row_values[4]
    contact_email = row_values[5]
    company_hours_raw = row_values[6]
    company_logo_url = row_values[7]
    google_map_src = row_values[8]
    target_location = row_values[9]
    services_offered = row_values[10]
    gallery_image_urls = row_values[11]
    youtube_video_url = row_values[12]
    linkedin_url = row_values[13]
    facebook_url = row_values[14]
    twitter_url = row_values[15]
    youtube_url = row_values[16]   
    # Processing company hours
    company_hours = company_hours_raw.split('\n') if company_hours_raw else []
    hours_html = "<br>".join(f"<span><i class='fas fa-clock'></i> {day}</span>" for day in company_hours)
    # Processing gallery images
    galleries = ""
    if gallery_image_urls:
        url_list = [url.strip() for url in gallery_image_urls.split(',')]
        gallery_images_html = "".join([f'<img src="{url}" alt="Photo {index + 1}">' for index, url in enumerate(url_list)])
        galleries = f"""<div class="company-info">
            <h2>Our Gallery</h2>
            <div class="gallery">{gallery_images_html}</div>
          </div>"""

    # Constructing the HTML content
    html1 = f"""<!-- wp:html --><div class="container">
          <div class="company-profile-header">
            <img src="{company_logo_url}" alt="Company Logo">
          </div>

          <div class="info-and-map">
            <div class="info-block">
              <div class="highlight">
                <h2>Contact Information</h2>
                <p><i class="fas fa-map-marker-alt"></i> Address: {complete_address}</p>
                <p><i class="fas fa-globe"></i> Website: <a href="{company_website}" target="_blank">{company_website}</a></p>
                <p><i class="fas fa-phone"></i> Phone: <a href="tel:+19312578004">{company_phone_number}</a></p>
                <p><i class="fas fa-envelope"></i> Email: <a href="mailto:{contact_email}">{contact_email}</a></p>
              </div>
              <div class="highlight">
                <h2>About Us</h2>
                <p>{hours_html}</p>
                <p><i class="fas fa-info-circle"></i> <strong>Description</strong>: {description}</p>
              </div>
            </div>
            <div class="map-container">
              <h2>Find Us On The Map</h2>
              <iframe src="{google_map_src}" style="width: 100%; height: 500px;" allowfullscreen></iframe>
            </div>
          </div>
         <div class="highlight">
            <h2>Brands/Services Offered</h2>
            <p>{services_offered}</p>
          </div>
            {galleries}
          <div class="company-info">
            <h2>Watch Our Video</h2>
            <iframe src="{youtube_video_url}" style="width: 65%; height: 400px;" allowfullscreen></iframe>
          </div>

          <div class="company-info">
            <h2>Connect With Us</h2>
            <div class="social-media">
              <a href="{linkedin_url}" target="_blank" rel="noopener"><i class="fab fa-linkedin-in"></i></a>
              <a href="{facebook_url}" target="_blank" rel="noopener"><i class="fab fa-facebook-f"></i></a>
              <a href="{twitter_url}" target="_blank" rel="noopener"><i class="fab fa-twitter"></i></a>
              <a href="{youtube_url}" target="_blank" rel="noopener"><i class="fab fa-youtube"></i></a>
            </div>
          </div>

        </div><!-- /wp:html -->"""
    # Preparing the post data
    post = {
        'title': company_name,
        'slug': company_name,
        'status': 'draft',
        'content': html1,
        # 'categories': 11,   # Uncomment and use as needed
        # 'featured_media': image_id  # Uncomment and use as needed
    }

    # Sending the POST request
    try:
        response = requests.post(url + '/posts', headers=header, json=post)
        print(response)
    except requests.RequestException as e:
        print(f"Error during request: {e}")
