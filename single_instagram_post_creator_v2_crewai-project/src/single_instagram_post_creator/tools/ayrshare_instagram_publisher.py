from crewai.tools import BaseTool
from pydantic import BaseModel, Field, validator
from typing import Type, Optional
import requests
import json
from datetime import datetime
import re

class AyrshareInstagramRequest(BaseModel):
    """Input schema for Ayrshare Instagram Publisher Tool."""
    post_text: str = Field(..., description="The caption/text for the Instagram post")
    image_url: Optional[str] = Field(None, description="URL of the image to post (optional)")
    schedule_date: Optional[str] = Field(None, description="Date to schedule the post (YYYY-MM-DD format, optional)")
    schedule_time: Optional[str] = Field(None, description="Time to schedule the post (HH:MM format, 24-hour, optional)")

    @validator('schedule_date')
    def validate_schedule_date(cls, v):
        if v is not None:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('schedule_date must be in YYYY-MM-DD format')
        return v

    @validator('schedule_time')
    def validate_schedule_time(cls, v):
        if v is not None:
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
                raise ValueError('schedule_time must be in HH:MM format (24-hour)')
        return v

    @validator('image_url')
    def validate_image_url(cls, v):
        if v is not None and v.strip():
            if not v.startswith(('http://', 'https://')):
                raise ValueError('image_url must be a valid HTTP/HTTPS URL')
        return v

class AyrshareInstagramPublisher(BaseTool):
    """Tool for posting content to Instagram via Ayrshare API with scheduling capabilities."""

    name: str = "ayrshare_instagram_publisher"
    description: str = (
        "Post content to Instagram via Ayrshare API. Supports text-only and image+text posts "
        "with optional scheduling. Returns success/failure status with post ID if successful."
    )
    args_schema: Type[BaseModel] = AyrshareInstagramRequest

    def _run(self, post_text: str, image_url: Optional[str] = None, 
             schedule_date: Optional[str] = None, schedule_time: Optional[str] = None) -> str:
        """
        Post content to Instagram via Ayrshare API.
        
        Args:
            post_text: The caption/text for the Instagram post
            image_url: URL of the image to post (optional)
            schedule_date: Date to schedule the post (YYYY-MM-DD format, optional)
            schedule_time: Time to schedule the post (HH:MM format, 24-hour, optional)
            
        Returns:
            JSON string with status, message, and post_id if successful
        """
        try:
            # API configuration
            api_url = "https://app.ayrshare.com/api/post"
            api_key = "F8170429-DB074903-B353B21B-C8334760"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Build request payload
            payload = {
                "post": post_text.strip(),
                "platforms": ["instagram"]
            }
            
            # Add image URL if provided
            if image_url and image_url.strip():
                payload["mediaUrls"] = [image_url.strip()]
            
            # Handle scheduling if both date and time are provided
            if schedule_date and schedule_time:
                try:
                    # Combine date and time into ISO format
                    datetime_str = f"{schedule_date}T{schedule_time}:00Z"
                    # Validate the combined datetime
                    datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                    payload["scheduleDate"] = datetime_str
                    is_scheduled = True
                except ValueError as e:
                    return json.dumps({
                        "status": "error",
                        "message": f"Invalid schedule date/time combination: {str(e)}",
                        "post_id": None
                    })
            elif schedule_date or schedule_time:
                return json.dumps({
                    "status": "error",
                    "message": "Both schedule_date and schedule_time must be provided for scheduling",
                    "post_id": None
                })
            else:
                is_scheduled = False
            
            # Make API request
            response = requests.post(
                api_url, 
                headers=headers, 
                json=payload, 
                timeout=30
            )
            
            # Handle API response
            if response.status_code == 200:
                response_data = response.json()
                
                # Extract post ID from response
                post_id = None
                if 'id' in response_data:
                    post_id = response_data['id']
                elif 'data' in response_data and isinstance(response_data['data'], dict):
                    post_id = response_data['data'].get('id')
                
                success_message = "Post published successfully to Instagram @kskk.2031"
                if is_scheduled:
                    success_message = f"Post scheduled successfully for {schedule_date} at {schedule_time} on Instagram @kskk.2031"
                
                return json.dumps({
                    "status": "success",
                    "message": success_message,
                    "post_id": post_id,
                    "scheduled": is_scheduled,
                    "schedule_time": f"{schedule_date} {schedule_time}" if is_scheduled else None
                })
            
            elif response.status_code == 401:
                return json.dumps({
                    "status": "error",
                    "message": "Authentication failed - invalid API key",
                    "post_id": None
                })
            
            elif response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', 'Bad request - check your parameters')
                except:
                    error_message = 'Bad request - invalid parameters or data format'
                
                return json.dumps({
                    "status": "error",
                    "message": f"API error: {error_message}",
                    "post_id": None
                })
            
            elif response.status_code == 429:
                return json.dumps({
                    "status": "error",
                    "message": "Rate limit exceeded - please try again later",
                    "post_id": None
                })
            
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"API request failed with status code {response.status_code}: {response.text}",
                    "post_id": None
                })
                
        except requests.exceptions.Timeout:
            return json.dumps({
                "status": "error",
                "message": "Request timed out - please check your internet connection and try again",
                "post_id": None
            })
        
        except requests.exceptions.ConnectionError:
            return json.dumps({
                "status": "error",
                "message": "Connection error - unable to reach Ayrshare API",
                "post_id": None
            })
        
        except requests.exceptions.RequestException as e:
            return json.dumps({
                "status": "error",
                "message": f"Network error: {str(e)}",
                "post_id": None
            })
        
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
                "post_id": None
            })