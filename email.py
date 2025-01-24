import logging
import textwrap
from dataclasses import dataclass
from email.utils import make_msgid, parseaddr
from typing import Any, Optional

import nh3
from flask_babel import gettext as __

from superset import app
from superset.exceptions import SupersetErrorsException
from superset.reports.models import ReportRecipientType
from superset.reports.notifications.base import BaseNotification
from superset.reports.notifications.exceptions import NotificationError
from superset.utils import json
from superset.utils.core import HeaderDataType, send_email_smtp
from superset.utils.decorators import statsd_gauge

logger = logging.getLogger(__name__)

# ... (keep existing TAG and ATTRIBUTE definitions)

@dataclass
class EmailContent:
    body: str
    header_data: Optional[HeaderDataType] = None
    data: Optional[dict[str, Any]] = None
    pdf: Optional[dict[str, bytes]] = None
    images: Optional[dict[str, bytes]] = None

class EmailNotification(BaseNotification):
    type = ReportRecipientType.EMAIL

    def _generate_comprehensive_email_template(self, content: Any) -> str:
        """
        Generate a more comprehensive and visually appealing email template
        """
        # Sanitize content
        description = nh3.clean(
            content.description or "",
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
        )

        # Prepare screenshots/images
        img_tags = []
        if content.screenshots:
            for screenshot in content.screenshots:
                msgid = make_msgid(self._get_smtp_domain())[1:-1]
                img_tags.append(
                    f"""
                    <div class="screenshot-container">
                        <img src="cid:{msgid}" alt="Report Screenshot" class="responsive-image">
                    </div>
                    """
                )
        img_content = "".join(img_tags)

        # Prepare table data if exists
        html_table = ""
        if content.embedded_data is not None:
            html_table = nh3.clean(
                content.embedded_data.to_html(na_rep="", index=True, escape=True),
                tags=TABLE_TAGS,
                attributes=ALLOWED_TABLE_ATTRIBUTES,
            )

        # Construct comprehensive email template
        email_template = textwrap.dedent(f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{self._get_subject()}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    line-height: 1.6;
                    color: #2a3f5f;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f4f6f9;
                }}
                .email-container {{
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    padding: 30px;
                }}
                .header {{
                    background-color: #007bff;
                    color: white;
                    padding: 15px;
                    text-align: center;
                    border-radius: 8px 8px 0 0;
                }}
                .content {{
                    margin-top: 20px;
                }}
                .screenshot-container {{
                    margin: 20px 0;
                    text-align: center;
                }}
                .responsive-image {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 8px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
                .cta-button {{
                    display: inline-block;
                    background-color: #007bff;
                    color: white;
                    padding: 10px 20px;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 15px;
                }}
                .footer {{
                    margin-top: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #6c757d;
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <h1>{content.name} Report</h1>
                </div>
                
                <div class="content">
                    <h2>Report Details</h2>
                    
                    <p>{description}</p>
                    
                    {img_content}
                    
                    {html_table}
                    
                    <div style="text-align: center;">
                        <a href="{content.url}" class="cta-button">{self._get_call_to_action()}</a>
                    </div>
                </div>
                
                <div class="footer">
                    <p>Generated by Superset | {app.config.get('EMAIL_REPORTS_SUBJECT_PREFIX', 'Analytics Report')}</p>
                    <p>Do not reply to this email</p>
                </div>
            </div>
        </body>
        </html>
        """)

        return email_template

    def _get_content(self) -> EmailContent:
        # Use the new comprehensive template generation method
        body = self._generate_comprehensive_email_template(self._content)
        
        images = {}
        if self._content.screenshots:
            images = {
                make_msgid(self._get_smtp_domain())[1:-1]: screenshot
                for screenshot in self._content.screenshots
            }

        csv_data = None
        if self._content.csv:
            csv_data = {__("%(name)s.csv", name=self._content.name): self._content.csv}

        pdf_data = None
        if self._content.pdf:
            pdf_data = {__("%(name)s.pdf", name=self._content.name): self._content.pdf}

        return EmailContent(
            body=body,
            images=images,
            pdf=pdf_data,
            data=csv_data,
            header_data=self._content.header_data,
        )

    # ... (rest of the existing methods remain the same)
