from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional, Dict, Any
import requests
import json
import time
import os

class BufferInstagramToolInput(BaseModel):
    """Input schema for Buffer Instagram Tool."""
    profile_id: str = Field(
        ...,
        description="Buffer profile ID for the Instagram account. Get this from Buffer's /profiles.json endpoint."
    )
    text: str = Field(
        ...,
        description="Caption/content for the Instagram post. Can include hashtags (#) and mentions (@)."
    )
    media: Optional[str] = Field(
        None,
        description="Image URL for the post. Must be a publicly accessible URL. Leave empty for text-only posts."
    )
    scheduled_at: Optional[int] = Field(
        None,
        description="Unix timestamp for scheduling the post. Leave empty for immediate posting."
    )
    top: bool = Field(
        False,
        description="Set to True to add post to top of queue, False for normal posting order."
    )

class BufferInstagramTool(BaseTool):
    """
    Tool for posting content to Instagram via Buffer API.
    
    This tool provides comprehensive Instagram posting capabilities through Buffer's API:
    - Post images with captions
    - Schedule posts for future times  
    - Support hashtags and mentions
    - Handle text-only posts
    - Get posting status and URLs
    
    SETUP INSTRUCTIONS:
    
    1. Create Buffer Developer Account:
       - Go to https://buffer.com/developers/apps
       - Create a new app to get your access token
    
    2. Connect Instagram Account:
       - Log into Buffer dashboard
       - Connect your Instagram business account
       - Note: Personal Instagram accounts require Instagram Business/Creator account
    
    3. Get Profile ID:
       - Use Buffer API endpoint: GET https://api.bufferapp.com/1/profiles.json?access_token=YOUR_TOKEN
       - Find your Instagram profile and copy the 'id' field
    
    4. Set Environment Variable:
       - Set BUFFER_API_KEY to your Buffer access token
    
    RATE LIMITS:
    - Buffer API allows 10 requests per minute
    - Tool includes automatic rate limiting handling
    
    BEST PRACTICES:
    - Use high-quality images (minimum 1080x1080 for Instagram)
    - Keep captions under 2,200 characters
    - Use relevant hashtags (limit 30 per post)
    - Schedule posts during peak engagement times
    - Always test with a single post before bulk operations
    """

    name: str = "buffer_instagram_tool"
    description: str = (
        "Post content to Instagram via Buffer API. Supports immediate posting, scheduling, "
        "images, text posts, hashtags, and mentions. Handles Buffer rate limits and provides "
        "detailed status information."
    )
    args_schema: Type[BaseModel] = BufferInstagramToolInput

    def _run(
        self, 
        profile_id: str, 
        text: str, 
        media: Optional[str] = None, 
        scheduled_at: Optional[int] = None, 
        top: bool = False
    ) -> str:
        """
        Execute the Buffer Instagram posting operation.
        
        Args:
            profile_id: Buffer profile ID for Instagram account
            text: Caption/content for the post
            media: Optional image URL
            scheduled_at: Optional Unix timestamp for scheduling
            top: Whether to add to top of queue
        
        Returns:
            JSON string with posting results and status information
        """
        try:
            # Get access token from environment
            access_token = os.getenv('BUFFER_API_KEY')
            if not access_token:
                return json.dumps({
                    "success": False,
                    "error": "BUFFER_API_KEY environment variable is required",
                    "setup_help": "Set your Buffer API access token as BUFFER_API_KEY environment variable"
                })

            # Validate inputs
            if not profile_id or not text:
                return json.dumps({
                    "success": False,
                    "error": "profile_id and text are required parameters"
                })

            # First, verify the profile exists and is valid
            profile_check = self._verify_profile(access_token, profile_id)
            if not profile_check["success"]:
                return json.dumps(profile_check)

            # Validate media URL if provided
            if media:
                media_check = self._validate_media_url(media)
                if not media_check["success"]:
                    return json.dumps(media_check)

            # Prepare the API request
            api_url = "https://api.bufferapp.com/1/updates/create.json"
            
            # Build request data
            post_data = {
                "access_token": access_token,
                "profile_ids[]": profile_id,
                "text": text,
                "top": "true" if top else "false"
            }

            # Add media if provided
            if media:
                post_data["media[link]"] = media

            # Add scheduling if provided
            if scheduled_at:
                # Validate timestamp is in the future
                current_time = int(time.time())
                if scheduled_at <= current_time:
                    return json.dumps({
                        "success": False,
                        "error": f"Scheduled time must be in the future. Current time: {current_time}, Provided: {scheduled_at}"
                    })
                post_data["scheduled_at"] = scheduled_at

            # Make the API request with rate limiting
            response = self._make_api_request(api_url, post_data)
            
            if response.status_code == 200:
                result_data = response.json()
                
                # Check if the response indicates success
                if "updates" in result_data and len(result_data["updates"]) > 0:
                    update = result_data["updates"][0]
                    
                    result = {
                        "success": True,
                        "buffer_id": update.get("id"),
                        "status": update.get("status"),
                        "scheduled_at": update.get("scheduled_at"),
                        "profile_service": update.get("profile_service"),
                        "text_length": len(text),
                        "has_media": media is not None,
                        "message": "Post successfully created in Buffer"
                    }
                    
                    # Add direct link if available
                    if "posted_at" in update and update["posted_at"]:
                        result["posted_at"] = update["posted_at"]
                        result["message"] = "Post successfully published to Instagram"
                    
                    return json.dumps(result, indent=2)
                else:
                    return json.dumps({
                        "success": False,
                        "error": "Unexpected response format from Buffer API",
                        "response": result_data
                    })
                    
            elif response.status_code == 429:
                return json.dumps({
                    "success": False,
                    "error": "Rate limit exceeded. Buffer allows 10 requests per minute.",
                    "retry_after": "Wait 60 seconds before trying again"
                })
            else:
                error_data = response.json() if response.content else {}
                return json.dumps({
                    "success": False,
                    "error": f"Buffer API error: {response.status_code}",
                    "details": error_data.get("error", "Unknown error"),
                    "status_code": response.status_code
                })

        except requests.exceptions.RequestException as e:
            return json.dumps({
                "success": False,
                "error": f"Network error connecting to Buffer API: {str(e)}",
                "troubleshooting": "Check your internet connection and Buffer API status"
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "type": type(e).__name__
            })

    def _verify_profile(self, access_token: str, profile_id: str) -> Dict[str, Any]:
        """Verify that the profile ID is valid and accessible."""
        try:
            profiles_url = "https://api.bufferapp.com/1/profiles.json"
            response = self._make_api_request(
                profiles_url, 
                {"access_token": access_token}, 
                method="GET"
            )
            
            if response.status_code == 200:
                profiles = response.json()
                
                # Find the matching profile
                target_profile = None
                for profile in profiles:
                    if profile.get("id") == profile_id:
                        target_profile = profile
                        break
                
                if target_profile:
                    if target_profile.get("service") != "instagram":
                        return {
                            "success": False,
                            "error": f"Profile {profile_id} is not an Instagram profile",
                            "actual_service": target_profile.get("service"),
                            "available_services": [p.get("service") for p in profiles]
                        }
                    
                    return {
                        "success": True,
                        "profile_name": target_profile.get("formatted_username"),
                        "service": target_profile.get("service")
                    }
                else:
                    available_profiles = [
                        {"id": p.get("id"), "service": p.get("service"), "username": p.get("formatted_username")} 
                        for p in profiles if p.get("service") == "instagram"
                    ]
                    
                    return {
                        "success": False,
                        "error": f"Profile ID {profile_id} not found",
                        "available_instagram_profiles": available_profiles
                    }
            else:
                return {
                    "success": False,
                    "error": f"Failed to fetch profiles: {response.status_code}",
                    "details": response.json() if response.content else "No response content"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error verifying profile: {str(e)}"
            }

    def _validate_media_url(self, media_url: str) -> Dict[str, Any]:
        """Validate that the media URL is accessible and appears to be an image."""
        try:
            # Make a HEAD request to check if URL is accessible
            response = requests.head(media_url, timeout=10, allow_redirects=True)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Media URL is not accessible: {response.status_code}",
                    "url": media_url
                }
            
            # Check content type if available
            content_type = response.headers.get('content-type', '').lower()
            if content_type and not content_type.startswith('image/'):
                return {
                    "success": False,
                    "error": f"URL does not appear to be an image. Content-Type: {content_type}",
                    "url": media_url
                }
            
            return {"success": True}
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Cannot access media URL: {str(e)}",
                "url": media_url
            }

    def _make_api_request(self, url: str, data: Dict[str, Any], method: str = "POST") -> requests.Response:
        """Make API request with proper headers and rate limiting."""
        headers = {
            "User-Agent": "CrewAI-BufferTool/1.0",
            "Accept": "application/json"
        }
        
        # Add small delay to respect rate limits
        time.sleep(6.1)  # Just over 6 seconds to stay under 10 requests per minute
        
        if method.upper() == "GET":
            return requests.get(url, params=data, headers=headers, timeout=30)
        else:
            return requests.post(url, data=data, headers=headers, timeout=30)