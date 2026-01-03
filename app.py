import os
import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import FieldFilter
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

app = Flask(__name__)

# Initialize Firebase
cred = credentials.Certificate("firebase-service-account.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# At the top, replace SMTP config:
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
FROM_EMAIL = "noreply.ssnlms@gmail.com"
BASE_URL = os.getenv("BASE_URL")

def get_gmail_service():
    """Create Gmail API service with refresh token"""
    creds = Credentials(
        token=None,
        refresh_token=GMAIL_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GMAIL_CLIENT_ID,
        client_secret=GMAIL_CLIENT_SECRET,
        scopes=['https://www.googleapis.com/auth/gmail.send']
    )
    return build('gmail', 'v1', credentials=creds)

def send_email(to_email, subject, html_body, text_body):
    """Send email via Gmail API"""
    try:
        service = get_gmail_service()
        
        # Create message
        message = MIMEMultipart('alternative')
        message['From'] = FROM_EMAIL
        message['To'] = to_email
        message['Subject'] = subject
        
        message.attach(MIMEText(text_body, 'plain'))
        message.attach(MIMEText(html_body, 'html'))
        
        # Encode and send
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        send_message = {'raw': raw_message}
        
        service.users().messages().send(
            userId='me', 
            body=send_message
        ).execute()
        
        print(f"✅ Email sent to {to_email} via Gmail API")
        return True
        
    except Exception as e:
        print(f"❌ Gmail API error: {e}")
        return False

def create_assignment_email_html(user_name: str, assignments: list, unsubscribe_token: str) -> str:
    """Create HTML email content for pending assignments"""
    assignment_rows = ""
    for idx, assignment in enumerate(assignments, 1):
        course_name = assignment.get('courseName', 'Unknown Course')
        if '---' in course_name:
            parts = course_name.split('---')
            course_name = f"{parts[0]} - {parts[1]}" if len(parts) > 1 else parts[0]
        
        due_date = assignment.get('dueDate', 'No due date')
        title = assignment.get('title') or 'Assignment'
        url = assignment.get('url', '#')
        status = assignment.get('status', 'pending')
        status_emoji = '⚠️' if status == 'overdue' else '⏰'
        
        assignment_rows += f"""
        <tr>
            <td style="padding: 15px; border-bottom: 1px solid #e9ecef;">
                <div style="margin-bottom: 5px;">
                    <strong style="font-size: 16px; color: #2c3e50;">{idx}. {title}</strong>
                </div>
                <div style="color: #6c757d; font-size: 14px; margin-left: 16px;">
                    📚 {course_name}
                </div>
                <div style="color: {'#dc3545' if status == 'overdue' else '#e74c3c'}; font-size: 14px; margin-left: 16px; margin-top: 5px;">
                    {status_emoji} Due: {due_date}
                </div>
                <div style="margin-left: 16px; margin-top: 8px;">
                    <a href="{url}" style="color: #007bff; text-decoration: none; font-size: 14px;">
                        View Assignment →
                    </a>
                </div>
            </td>
        </tr>
        """
    
    unsubscribe_url = f"{BASE_URL}/unsubscribe?token={unsubscribe_token}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8f9fa;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px;">📚 LMS Helper</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 16px;">Daily Assignment Reminder</p>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <p style="font-size: 16px; color: #2c3e50; margin-top: 0;">
                    Dear Student! 👋
                </p>
                
                <p style="font-size: 16px; color: #2c3e50;">
                    You have <strong style="color: #e74c3c;">{len(assignments)} pending assignment(s)</strong> that need your attention.
                </p>
                
                <div style="margin: 25px 0;">
                    <table style="width: 100%; border-collapse: collapse; background: #f8f9fa; border-radius: 8px; overflow: hidden;">
                        {assignment_rows}
                    </table>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://lms.ssn.edu.in" 
                       style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                              color: white; padding: 12px 30px; text-decoration: none; border-radius: 25px; 
                              font-weight: 500; font-size: 16px;">
                        Open LMS →
                    </a>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef; text-align: center;">
                    <a href="{unsubscribe_url}" 
                       style="display: inline-block; background-color: #6c757d; color: white; 
                              padding: 8px 20px; text-decoration: none; border-radius: 20px; 
                              font-size: 13px; margin-bottom: 10px;">
                        🔕 Stop receiving these emails
                    </a>
                    <p style="color: #6c757d; font-size: 12px; margin: 10px 0 5px 0;">
                        This is an automated reminder from LMS Helper
                    </p>
                    <p style="color: #6c757d; font-size: 12px; margin: 5px 0;">
                        Sent on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

def send_assignment_reminders():
    """Send email reminders to all users with assignments"""
    try:
        print("📧 Starting assignment reminder job...")
        
        users_ref = db.collection("users")
        query = users_ref.where(filter=FieldFilter("email_notifications", "==", True))
        
        sent_count = 0
        error_count = 0
        
        for user_doc in query.stream():
            try:
                user_data = user_doc.to_dict()
                user_email = user_data.get("email")
                user_name = user_data.get("name", "Student")
                unsubscribe_token = user_data.get("unsubscribe_token")
                
                if not user_email or not unsubscribe_token:
                    print(f"⚠️ Skipping user - missing email or token")
                    continue
                
                # Get user's assignments
                assignments_ref = user_doc.reference.collection("assignments")
                assignments = []
                for assignment_doc in assignments_ref.stream():
                    assignment = assignment_doc.to_dict()
                    assignment["id"] = assignment_doc.id
                    assignments.append(assignment)
                
                # Skip if no assignments
                if not assignments:
                    print(f"ℹ️ No assignments for {user_email}, skipping")
                    continue
                
                # Create email content
                html_content = create_assignment_email_html(user_name, assignments, unsubscribe_token)
                
                text_content = f"""
Hi {user_name}!

You have {len(assignments)} pending assignment(s):

"""
                for idx, assignment in enumerate(assignments, 1):
                    course = assignment.get('courseName', 'Unknown Course')
                    due = assignment.get('dueDate', 'No due date')
                    status = assignment.get('status', 'pending')
                    text_content += f"{idx}. [{status.upper()}] {course}\n   Due: {due}\n\n"
                
                text_content += f"""
Visit https://lms.ssn.edu.in to view and submit your assignments.

To stop receiving these emails, visit:
{BASE_URL}/unsubscribe?token={unsubscribe_token}

---
This is an automated reminder from LMS Helper
"""
                
                # Send email
                success = send_email(
                    to_email=user_email,
                    subject=f"📚 LMS Helper: {len(assignments)} Pending Assignment(s)",
                    html_body=html_content,
                    text_body=text_content
                )
                
                if success:
                    sent_count += 1
                    print(f"✅ Sent reminder to {user_email} ({len(assignments)} assignments)")
                else:
                    error_count += 1
                    print(f"❌ Failed to send to {user_email}")
                    
            except Exception as user_error:
                error_count += 1
                print(f"❌ Error processing user {user_doc.id}: {str(user_error)}")
                continue
        
        result_msg = f"Reminder job complete: {sent_count} sent, {error_count} errors"
        print(f"✅ {result_msg}")
        
        return {
            "success": True,
            "sent": sent_count,
            "errors": error_count,
            "message": result_msg
        }
        
    except Exception as e:
        error_msg = f"Reminder job failed: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": error_msg
        }

@app.route("/")
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "online",
        "service": "LMS Helper Email Reminder Service",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/send-reminders", methods=["POST", "GET"])
def trigger_reminders():
    """Endpoint to trigger reminder emails"""
    result = send_assignment_reminders()
    return jsonify(result), 200 if result.get("success") else 500

@app.route("/unsubscribe")
def unsubscribe():
    """Handle unsubscribe requests"""
    from flask import request
    token = request.args.get("token")
    if not token:
        return "Invalid link", 400
    
    try:
        users_ref = db.collection("users")
        query = users_ref.where(filter=FieldFilter("unsubscribe_token", "==", token)).limit(1)
        docs = list(query.stream())
        
        if not docs:
            return "Invalid or expired link", 400
        
        docs[0].reference.update({
            "email_notifications": False,
            "unsubscribed_at": firestore.SERVER_TIMESTAMP
        })
        
        print(f"🔕 User unsubscribed: {docs[0].id}")
        
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    background: white;
                    padding: 40px;
                    border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                    text-align: center;
                    max-width: 400px;
                }
                h3 {
                    color: #2c3e50;
                    margin-top: 0;
                }
                p {
                    color: #6c757d;
                }
                .emoji {
                    font-size: 48px;
                    margin-bottom: 20px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="emoji">🔕</div>
                <h3>You're Unsubscribed</h3>
                <p>You will no longer receive assignment reminder emails from LMS Helper.</p>
                <p style="font-size: 12px; margin-top: 20px;">
                    You can always re-enable notifications from the LMS Helper extension.
                </p>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        print(f"❌ Unsubscribe error: {str(e)}")
        return "An error occurred", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)