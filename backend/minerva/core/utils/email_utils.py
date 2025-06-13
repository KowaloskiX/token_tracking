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

async def send_email(
    to_email: str,
    subject: str,
    message: str,
    title: str | None = None,
    action_url: str | None = None,
    action_text: str | None = None,
):
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


def build_tender_results_email_html(
    analysis_name: str,
    analysis_id: str,
    tenders: list,
) -> str:
    """Generate HTML content for tender results email."""
    frontend_url = os.getenv("FRONTEND_URL", "https://www.asystent.ai")

    # Filter tenders by score > 0.6 and sort by score descending
    filtered_tenders = [
        tender for tender in tenders 
        if getattr(tender, "tender_score", 0) > 0.6
    ]
    sorted_tenders = sorted(
        filtered_tenders, 
        key=lambda t: getattr(t, "tender_score", 0), 
        reverse=True
    )

    sections: list[str] = []
    for tender in sorted_tenders:
        tender_name = (
            tender.tender_metadata.name
            if getattr(tender, "tender_metadata", None)
            and getattr(tender.tender_metadata, "name", None)
            else "Unknown Tender"
        )
        tender_desc = getattr(tender, "tender_description", "") or ""
        tender_id = (
            str(getattr(tender, "id", "")) if getattr(tender, "id", None) else ""
        )
        tender_score = getattr(tender, "tender_score", 0)

        link = f"{frontend_url}/dashboard/tenders/{analysis_id}"
        if tender_id:
            link += f"?tenderId={tender_id}"

        # Format score with color coding
        score_percentage = round(tender_score * 100)
        score_color = "#28a745" if tender_score >= 0.65 else "#6c757d"  # Green if >= 0.65, gray otherwise
        score_indicator = f'<span style="background-color: {score_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">Relewantność: {score_percentage}%</span>'

        sections.append(
            f"<h3><a href='{link}'>{tender_name}</a></h3><p style='margin-top: 8px; margin-bottom: 8px;'>{score_indicator}</p><p>{tender_desc}</p>"
        )

    if sections:
        message = "".join(sections)
    else:
        message = "Nie znaleziono dzisiaj przetargów spełniających kryteria (wynik > 60%)."

    return render_email_template(
        title=f"Nowe przetargi - '{analysis_name}'",
        message=message,
    )
