import os
import requests
import json

class EmailService:
    def __init__(self):
        self.api_token = os.getenv('POSTMARK_API_TOKEN')
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.api_url = "https://api.postmarkapp.com/email"

    def send_video_email(self, to_email: str, video_url: str):
        """
        Send an email with the video link using Postmark
        """
        if not self.api_token or not self.sender_email:
            print("Postmark credentials not found. Skipping email.")
            return False

        if not to_email:
            print("No recipient email provided. Skipping email.")
            return False

        print(f"Sending video email to {to_email}")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": self.api_token
        }

        # HTML body for the email
        html_body = f"""
        <html>
          <body>
            <h2>Your Story Video is Ready!</h2>
            <p>Hello,</p>
            <p>Your video has been successfully generated and is ready for viewing.</p>
            <p>You can watch and download it using the link below:</p>
            <p>
              <a href="{video_url}" style="background-color: #4CAF50; color: white; padding: 14px 25px; text-align: center; text-decoration: none; display: inline-block; border-radius: 4px;">
                Watch Your Video
              </a>
            </p>
            <p>Or copy this link: {video_url}</p>
            <p>Thank you for using Story Catcher!</p>
          </body>
        </html>
        """

        payload = {
            "From": self.sender_email,
            "To": to_email,
            "Subject": "Your Story Video is Ready!",
            "HtmlBody": html_body,
            "MessageStream": "outbound"
        }

        try:
            response = requests.post(self.api_url, headers=headers, data=json.dumps(payload))
            
            if response.status_code == 200:
                print(f"Email sent successfully to {to_email}")
                return True
            else:
                print(f"Failed to send email. Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False
