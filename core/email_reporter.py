import json
import smtplib
from email.message import EmailMessage

from config.settings import settings
from core.logger import logger

# SMTP / UI copy — matches project-job-application-engine (README: Job Application Engine)
APPLICATION_NAME = "Job Application Engine"


class EmailReporter:
    @staticmethod
    def send_report(output_json_path: str):
        """
        Reads the output.json file and sends an HTML report via SMTP.
        """
        # Validate SMTP configuration
        if not all([settings.SMTP_SERVER, settings.SMTP_USERNAME, settings.SMTP_PASSWORD]):
            logger.warning("[EMAIL] SMTP configurations are not fully set up. Skipping email report.")
            return

        try:
            with open(output_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"[EMAIL] Failed to open/parse {output_json_path}: {e}")
            return

        display_name = data.get("candidate_name", "Unknown Candidate")

        # HTML Template
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f4f7f6; color: #333; margin: 0; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: #ffffff; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">{APPLICATION_NAME} — run report</h2>
                    
                    <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                        <tr>
                            <th style="text-align: left; padding: 8px; border-bottom: 1px solid #eee; width: 40%; color: #7f8c8d;">Status</th>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold; color: {'#27ae60' if data.get('status') == 'success' else '#e74c3c'};">
                                {str(data.get('status')).upper()}
                            </td>
                        </tr>
                        <tr>
                            <th style="text-align: left; padding: 8px; border-bottom: 1px solid #eee; color: #7f8c8d;">Candidate</th>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{display_name}</td>
                        </tr>
                        <tr>
                            <th style="text-align: left; padding: 8px; border-bottom: 1px solid #eee; color: #7f8c8d;">Started At</th>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{data.get('started_at', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th style="text-align: left; padding: 8px; border-bottom: 1px solid #eee; color: #7f8c8d;">Finished At</th>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{data.get('finished_at', 'N/A')}</td>
                        </tr>
                        <tr>
                            <th style="text-align: left; padding: 8px; border-bottom: 1px solid #eee; color: #7f8c8d;">Applications Submitted</th>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold; color: #2980b9;">{data.get('execution_summary', {}).get('total_applications_successful', 0)}</td>
                        </tr>
                        <tr>
                            <th style="text-align: left; padding: 8px; color: #7f8c8d;">Errors / Failed</th>
                            <td style="padding: 8px; color: #e74c3c;">{data.get('execution_summary', {}).get('total_applications_failed', 0)}</td>
                        </tr>
                    </table>

                    <p style="font-size: 13px; color: #95a5a6; margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px; text-align: center;">
                        {APPLICATION_NAME} · weekly workflow automation
                    </p>
                </div>
            </body>
        </html>
        """

        msg = EmailMessage()
        
        # Determine total success from new schema
        success_count = data.get('execution_summary', {}).get('total_applications_successful', 0)
        
        msg["Subject"] = (
            f"[{APPLICATION_NAME}] {display_name} — {success_count} applied"
        )
        msg['From'] = settings.SENDER_EMAIL or settings.SMTP_USERNAME
        msg['To'] = settings.REPORT_RECEIVER_EMAIL
        
        msg.set_content(
            f"{APPLICATION_NAME}: please enable HTML to view this report. "
            f"The run summary JSON ({APPLICATION_NAME} output) is attached."
        )
        msg.add_alternative(html_content, subtype='html')

        # Attach the JSON file
        try:
            with open(output_json_path, 'rb') as f:
                json_data = f.read()
            msg.add_attachment(
                json_data,
                maintype="application",
                subtype="json",
                filename="job-application-engine-output.json",
            )
            logger.info("[EMAIL] Attached job-application-engine-output.json to the email.")
        except Exception as file_err:
            logger.warning(f"[EMAIL] Could not attach JSON report: {file_err}")

        # Send the email
        try:
            logger.info(f"[EMAIL] connecting to {settings.SMTP_SERVER}:{settings.SMTP_PORT} to send report...")
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"[EMAIL] Successfully sent report to {settings.REPORT_RECEIVER_EMAIL}")
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send email: {e}")

email_reporter = EmailReporter()
