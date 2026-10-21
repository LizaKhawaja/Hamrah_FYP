import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings


def _send_email(to_email: str, subject: str, body: str):

    message = MIMEMultipart()
    message["From"] = settings.email_user
    message["To"] = to_email
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(settings.email_host, settings.email_port)
        server.starttls()
        server.login(settings.email_user, settings.email_pass)
        server.send_message(message)
        server.quit()
        print(f"Email sent successfully to {to_email}")
    except Exception as e:
        print("\n" + "="*60)
        print(f" EMAIL SMTP CONNECTION FAILED: {e}")
        print(" [LOCAL DEV FALLBACK] Showing outgoing message below:")
        print(f"   To:      {to_email}")
        print(f"   Subject: {subject}")
        print(f"   Body:    {body.strip()}")
        print("="*60 + "\n")
        
        print("⚠️ Warning: Suppressing SMTP error to allow local application flow to continue.")
        return


def send_otp_email(to_email: str, otp: str):
    subject = "OTP Verification Code"

    body = f"""
Hello,

Your OTP code is: {otp}

This OTP will expire in 3 minutes.

If you did not request this, please ignore this email.

Thank you.
"""

    _send_email(to_email, subject, body)

def send_forgot_password_otp_email(to_email: str, otp: str):
    subject = "Password Reset OTP"

    body = f"""
Hello,

You requested to reset your password.

Your OTP code is: {otp}

This OTP will expire in 3 minutes.

If you did not request this, please ignore this email.

Thank you.
"""

    _send_email(to_email, subject, body)


def send_reset_email(to_email: str, reset_link: str):
    subject = "Password Reset Request"

    body = f"""
Hello,

You requested to reset your password.

Click the link below to reset your password:

{reset_link}

This link will expire in 15 minutes.

If you did not request this, please ignore this email.

Thank you.
"""

    _send_email(to_email, subject, body)