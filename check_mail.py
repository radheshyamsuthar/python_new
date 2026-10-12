import smtplib
import ssl
from email.message import EmailMessage

# Setup sender and receiver credentials
#sender_email = "radhe.suthar86@gmail.com"
sender_email = "office@hkiinternationalexchange.com"
# Paste the 16-character App Password here (do not use your regular password)
#app_password = "aykrbysnaawrmgpw" 
app_password ="CYEQLfsPNKJ5qkKVZctK"
receiver_email = "radhe.suthar86@gmail.com"

# Create the email message
msg = EmailMessage()
msg["From"] = sender_email
msg["To"] = receiver_email
msg["Subject"] = "Automated Test Email via Python"
msg.set_content("Hello! This is a test email sent programmatically using Python and Gmail SMTP.")

# Securely connect to Gmail's SMTP server using SSL on port 465
#smtp_server = "smtp.gmail.com"
smtp_server = "mail.hkiinternationalexchange.com"
port = 465
#port = 587

# Create a secure SSL context
context = ssl.create_default_context()

try:
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        # Authenticate with the server
        server.login(sender_email, app_password)
        
        # Send the message
        server.send_message(msg)
        print("🎉 Email sent successfully!")
        
except Exception as e:
    print(f"An error occurred: {e}")
