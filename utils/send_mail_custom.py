from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

def send_custom_email(email, generated_code):
    subject = 'Your Confirmation Code'
    # Render the HTML template
    html_content = render_to_string('users/email_code.html', {"confirmation_code": generated_code})
    # Generate the plain text version
    text_content = strip_tags(html_content)
    from_email = settings.EMAIL_HOST_USER

    # Create an EmailMultiAlternatives object
    msg = EmailMultiAlternatives(subject, text_content, from_email, [email])
    msg.attach_alternative(html_content, "text/html")

    # Optionally, add extra headers to improve deliverability
    msg.extra_headers = {
        "X-Mailer": "Django",  # Identifies the software sending the email
        "Reply-To": from_email,  # Uncomment if you want to set a Reply-To address
        # "List-Unsubscribe": "<mailto:unsubscribe@yourdomain.com>"  # Uncomment if applicable
    }

    msg.send()