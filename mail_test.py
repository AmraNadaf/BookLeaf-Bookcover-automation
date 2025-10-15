# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
#
# # -------------------- CONFIG --------------------
# EMAIL_ADDRESS = "amranadaf@gmail.com"
# EMAIL_PASSWORD = "#"  # Use app password if using Gmail
#
# def send_email(recipient_email, email_body, subject="Book Cover Feedback"):
#     """Send email to author"""
#     try:
#         # Compose email
#         msg = MIMEMultipart()
#         msg['From'] = EMAIL_ADDRESS
#         msg['To'] = recipient_email
#         msg['Subject'] = subject
#         msg.attach(MIMEText(email_body, 'plain'))
#
#         # Connect to Gmail SMTP server
#         server = smtplib.SMTP('smtp.gmail.com', 587)
#         server.starttls()
#         server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
#         server.send_message(msg)
#         server.quit()
#
#         print(f"✅ Email sent to {recipient_email}")
#         return True
#     except Exception as e:
#         print(f"❌ Failed to send email to {recipient_email}: {e}")
#         return False
#
# email_body = 'hi'
# mail_test= send_email('amraspacestars@gmail.com', email_body)
