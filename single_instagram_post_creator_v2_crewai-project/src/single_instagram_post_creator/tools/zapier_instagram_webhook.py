from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Optional
import requests
import json
from datetime import datetime

class ZapierInstagramWebhookInput(BaseModel):
    """Input schema for Zapier Instagram Webhook Tool."""
    content: str = Field(..., description="The post caption/text content")
    media_urls: Optional[List[str]] = Field(default=None, description="List of image URLs (optional)")
    preferred_posting_time: str = Field(..., description="The preferred posting time (e.g., '1:10 PM')")
    timezone: str = Field(..., description="The timezone for posting (e.g., 'EST')")
    hashtags: Optional[List[str]] = Field(default=None, description="List of hashtags without # symbol (optional)")
    brand_name: Optional[str] = Field(default=None, description="Brand name (optional)")

class ZapierInstagramWebhookTool(BaseTool):
    """Tool for sending Instagram post data to Zapier webhook for automated posting."""

    name: str = "zapier_instagram_webhook"
    description: str = (
        "Sends Instagram post data to a Zapier webhook for automated posting. "
        "Handles content, media URLs, posting time, timezone, hashtags and brand information. "
        "Returns webhook confirmation on success or detailed error message on failure."
    )
    args_schema: Type[BaseModel] = ZapierInstagramWebhookInput

    def _run(self, content: str, preferred_posting_time: str, timezone: str, 
             media_urls: Optional[List[str]] = None, hashtags: Optional[List[str]] = None, 
             brand_name: Optional[str] = None) -> str:
        """
        Send Instagram post data to Zapier webhook.
        
        Args:
            content: The post caption/text content
            preferred_posting_time: The preferred posting time
            timezone: The timezone for posting  
            media_urls: List of image URLs (optional)
            hashtags: List of hashtags (optional)
            brand_name: Brand name (optional)
            
        Returns:
            str: Success confirmation or error message with details
        """
        
        webhook_url = ""
        timestamp = datetime.now().isoformat()
        
        try:
            # Format hashtags if provided
            formatted_hashtags = []
            if hashtags:
                formatted_hashtags = [f"#{tag.lstrip('#')}" for tag in hashtags]
            
            # Combine content with hashtags
            full_content = content
            if formatted_hashtags:
                full_content += " " + " ".join(formatted_hashtags)
            
            # Prepare JSON payload
            payload = {
                "content": full_content,
                "media_urls": media_urls or [],
                "preferred_posting_time": preferred_posting_time,
                "timezone": timezone,
                "account": "@kskk.2031",
                "post_type": "feed",
                "brand_name": brand_name
            }
            
            # Set headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "CrewAI-InstagramWebhookTool/1.0"
            }
            
            # Send POST request to webhook
            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            # Handle different response codes
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    return (
                        f"✅ SUCCESS: Instagram post data sent to Zapier webhook successfully!\n"
                        f"📅 Timestamp: {timestamp}\n"
                        f"📱 Account: @kskk.2031\n"
                        f"⏰ Preferred posting time: {preferred_posting_time} {timezone}\n"
                        f"📝 Content length: {len(content)} characters\n"
                        f"📸 Media URLs: {len(media_urls or [])} items\n"
                        f"🏷️ Hashtags: {len(hashtags or [])} items\n"
                        f"🔗 Webhook response: {response_data}\n"
                        f"🌐 Response status: {response.status_code}"
                    )
                except json.JSONDecodeError:
                    return (
                        f"✅ SUCCESS: Instagram post data sent to Zapier webhook!\n"
                        f"📅 Timestamp: {timestamp}\n"
                        f"📱 Account: @kskk.2031\n"
                        f"⏰ Preferred posting time: {preferred_posting_time} {timezone}\n"
                        f"🌐 Response status: {response.status_code}\n"
                        f"📄 Response text: {response.text}"
                    )
            elif response.status_code == 400:
                return (
                    f"❌ FAILURE: Bad request to Zapier webhook\n"
                    f"📅 Timestamp: {timestamp}\n"
                    f"🌐 Status code: {response.status_code}\n"
                    f"📄 Error response: {response.text}\n"
                    f"💡 Suggestion: Check the payload format and required fields"
                )
            elif response.status_code == 401:
                return (
                    f"❌ FAILURE: Unauthorized access to Zapier webhook\n"
                    f"📅 Timestamp: {timestamp}\n"
                    f"🌐 Status code: {response.status_code}\n"
                    f"💡 Suggestion: Verify the webhook URL is correct"
                )
            elif response.status_code == 404:
                return (
                    f"❌ FAILURE: Zapier webhook not found\n"
                    f"📅 Timestamp: {timestamp}\n"
                    f"🌐 Status code: {response.status_code}\n"
                    f"💡 Suggestion: Verify the webhook URL exists and is active"
                )
            elif response.status_code >= 500:
                return (
                    f"❌ FAILURE: Zapier server error\n"
                    f"📅 Timestamp: {timestamp}\n"
                    f"🌐 Status code: {response.status_code}\n"
                    f"📄 Error response: {response.text}\n"
                    f"💡 Suggestion: Try again later, this may be a temporary Zapier issue"
                )
            else:
                return (
                    f"⚠️ WARNING: Unexpected response from Zapier webhook\n"
                    f"📅 Timestamp: {timestamp}\n"
                    f"🌐 Status code: {response.status_code}\n"
                    f"📄 Response: {response.text}"
                )
                
        except requests.exceptions.ConnectionError:
            return (
                f"❌ FAILURE: Connection error to Zapier webhook\n"
                f"📅 Timestamp: {timestamp}\n"
                f"🌐 URL: {webhook_url}\n"
                f"💡 Suggestion: Check internet connection or webhook URL availability"
            )
        except requests.exceptions.Timeout:
            return (
                f"❌ FAILURE: Request timeout to Zapier webhook\n"
                f"📅 Timestamp: {timestamp}\n"
                f"⏱️ Timeout: 30 seconds\n"
                f"💡 Suggestion: Try again later or check network connection"
            )
        except requests.exceptions.RequestException as e:
            return (
                f"❌ FAILURE: Request error to Zapier webhook\n"
                f"📅 Timestamp: {timestamp}\n"
                f"❗ Error: {str(e)}\n"
                f"💡 Suggestion: Check request parameters and network connection"
            )
        except Exception as e:
            return (
                f"❌ FAILURE: Unexpected error occurred\n"
                f"📅 Timestamp: {timestamp}\n"
                f"❗ Error: {str(e)}\n"
                f"💡 Suggestion: Check all input parameters and try again"
            )
