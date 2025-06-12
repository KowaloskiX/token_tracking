import os
import httpx
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

# Set up Jinja2 environment to load templates from the templates directory.
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)

async def handle_send_email(to_email: str, subject: str, html: str):
    """
    Sends an email using the Resend API with raw HTML content.

    Args:
        to_email (str): Recipient's email address.
        subject (str): Subject of the email.
        html (str): HTML content of the email.

    Returns:
        dict: JSON response from the Resend API.

    Raises:
        Exception: If the RESEND_API_KEY environment variable is missing.
        httpx.HTTPStatusError: If the API request fails.
    """
    # Retrieve the Resend API key from environment variables
    resend_api_key = os.getenv("RESEND_API_KEY")
    if not resend_api_key:
        raise Exception("Missing RESEND_API_KEY environment variable")
    
    # Set up headers for the API request
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json"
    }
    
    # Prepare the payload for the API request
    payload = {
        "from": "AsystentAI <hello@asystent.ai>",  # Sender's email address with display name
        "to": to_email,                # Recipient's email address
        "subject": subject,            # Email subject
        "html": html                   # Email content in HTML format
    }
    
    # Send the email using an asynchronous HTTP client
    async with httpx.AsyncClient() as client:
        response = await client.post("https://api.resend.com/emails", json=payload, headers=headers)
        response.raise_for_status()  # Raise an error if the request fails
    
    # Return the API response as JSON
    return response.json()

def render_email_template(title: str, message: str, action_url: str = None, action_text: str = None) -> str:
    """
    Renders the email template with the provided dynamic data.

    Args:
        title (str): Title of the email.
        message (str): Main message content of the email.
        action_url (str, optional): URL for the action button. Defaults to None.
        action_text (str, optional): Text for the action button. Defaults to None.

    Returns:
        str: Rendered HTML content of the email.
    """
    # Load the email template and render it with the provided data
    template = jinja_env.get_template("email_template.html")
    return template.render(
        title=title,                  # Title of the email
        message=message,              # Main message content
        action_url=action_url,        # URL for the action button (if any)
        action_text=action_text,      # Text for the action button (if any)
        current_year=datetime.now().year  # Current year for the footer
    )

async def send_email(to_email: str, subject: str, message: str, title: str = None, action_url: str = None, action_text: str = None):
    """
    Renders the email template with the provided dynamic data and sends it.

    Args:
        to_email (str): Recipient's email address.
        subject (str): Subject of the email.
        message (str): Main message content of the email.
        title (str, optional): Title of the email. Defaults to None.
        action_url (str, optional): URL for the action button. Defaults to None.
        action_text (str, optional): Text for the action button. Defaults to None.

    Returns:
        dict: JSON response from the Resend API.

    Notes:
        - The subject will be prefixed with "Asystent AI - ".
        - If `title` is not provided, it will default to the subject (without the prefix).
        - If `action_url` is provided but `action_text` is not, the button text defaults to "Kliknij!".
    """
    # Use subject as title if title is not provided
    if title is None:
        title = subject

    # Provide a default button text if action_url is provided but action_text is not
    if action_url and not action_text:
        action_text = "Kliknij!"

    # Prefix the subject with "Asystent AI - "
    full_subject = f"Asystent AI - {subject}"
    
    # Render the email template with the provided data
    html_content = render_email_template(title, message, action_url, action_text)
    
    # Send the email using the handle_send_email function
    return await handle_send_email(to_email, full_subject, html_content)