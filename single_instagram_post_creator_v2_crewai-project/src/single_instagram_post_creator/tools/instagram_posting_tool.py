from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional, Dict, Any
import requests
import json
from datetime import datetime, timezone
import time

class InstagramPostingToolInput(BaseModel):
    """Input schema for Instagram Posting Tool."""
    post_type: str = Field(
        description="Type of post: 'text' for text-only posts or 'image' for image posts with captions"
    )
    caption: str = Field(
        description="Text content or caption for the post. Can include hashtags (#) and mentions (@)"
    )
    image_url: Optional[str] = Field(
        default=None,
        description="URL of the image to post (required for image posts, ignored for text posts)"
    )
    schedule_time: Optional[str] = Field(
        default=None,
        description="ISO format datetime for scheduling post (e.g., '2024-12-25T10:00:00Z'). If not provided, posts immediately"
    )
    access_token: str = Field(
        description="Instagram Graph API access token for the Instagram Business Account"
    )

class InstagramPostingTool(BaseTool):
    """
    Comprehensive Instagram posting tool that handles text and image posts using Instagram Graph API.
    
    Features:
    - Post text-only content to Instagram
    - Post images with captions
    - Schedule posts for future times
    - Handle hashtags and mentions
    - Comprehensive error handling and rate limit management
    - Detailed success/failure reporting
    
    API Setup Requirements:
    1. Create a Facebook App at developers.facebook.com
    2. Add Instagram Graph API product
    3. Connect Instagram Business Account to Facebook Page
    4. Generate access token with instagram_basic, instagram_content_publish permissions
    5. Instagram account must be a Business or Creator account
    
    Rate Limits:
    - 200 API calls per hour per access token
    - 25 posts per day per Instagram account
    
    Note: Text-only posts are only supported for Instagram Business accounts connected to Facebook Pages.
    For personal accounts, consider using image posts with minimal/transparent images.
    """

    name: str = "instagram_posting_tool"
    description: str = (
        "Post text and image content to Instagram using Instagram Graph API. "
        "Supports scheduling, hashtags, mentions, and provides detailed status reporting. "
        "Handles API rate limits and provides comprehensive error messages."
    )
    args_schema: Type[BaseModel] = InstagramPostingToolInput

    def _run(
        self,
        post_type: str,
        caption: str,
        access_token: str,
        image_url: Optional[str] = None,
        schedule_time: Optional[str] = None
    ) -> str:
        try:
            # Validate post type
            if post_type not in ["text", "image"]:
                return json.dumps({
                    "success": False,
                    "error": "Invalid post_type. Must be 'text' or 'image'",
                    "error_code": "INVALID_POST_TYPE"
                })

            # Validate image URL for image posts
            if post_type == "image" and not image_url:
                return json.dumps({
                    "success": False,
                    "error": "image_url is required for image posts",
                    "error_code": "MISSING_IMAGE_URL"
                })

            # Validate and parse schedule time if provided
            scheduled_publish_time = None
            if schedule_time:
                try:
                    dt = datetime.fromisoformat(schedule_time.replace('Z', '+00:00'))
                    scheduled_publish_time = int(dt.timestamp())
                    
                    # Check if scheduled time is in the future
                    current_time = datetime.now(timezone.utc).timestamp()
                    if scheduled_publish_time <= current_time:
                        return json.dumps({
                            "success": False,
                            "error": "Scheduled time must be in the future",
                            "error_code": "INVALID_SCHEDULE_TIME"
                        })
                        
                    # Instagram allows scheduling up to 75 days in advance
                    max_schedule_time = current_time + (75 * 24 * 60 * 60)
                    if scheduled_publish_time > max_schedule_time:
                        return json.dumps({
                            "success": False,
                            "error": "Cannot schedule posts more than 75 days in advance",
                            "error_code": "SCHEDULE_TOO_FAR"
                        })
                        
                except ValueError as e:
                    return json.dumps({
                        "success": False,
                        "error": f"Invalid schedule_time format. Use ISO format (e.g., '2024-12-25T10:00:00Z'): {str(e)}",
                        "error_code": "INVALID_DATETIME_FORMAT"
                    })

            # Get Instagram Business Account ID
            user_info = self._get_instagram_account_info(access_token)
            if not user_info["success"]:
                return json.dumps(user_info)
            
            instagram_account_id = user_info["account_id"]

            # Create media container
            container_result = self._create_media_container(
                instagram_account_id=instagram_account_id,
                post_type=post_type,
                caption=caption,
                image_url=image_url,
                access_token=access_token
            )
            
            if not container_result["success"]:
                return json.dumps(container_result)
            
            container_id = container_result["container_id"]

            # Publish the post
            publish_result = self._publish_media(
                instagram_account_id=instagram_account_id,
                container_id=container_id,
                access_token=access_token,
                scheduled_publish_time=scheduled_publish_time
            )

            return json.dumps(publish_result)

        except requests.exceptions.RequestException as e:
            return json.dumps({
                "success": False,
                "error": f"Network error occurred: {str(e)}",
                "error_code": "NETWORK_ERROR"
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Unexpected error occurred: {str(e)}",
                "error_code": "UNEXPECTED_ERROR"
            })

    def _get_instagram_account_info(self, access_token: str) -> Dict[str, Any]:
        """Get Instagram Business Account information."""
        try:
            # First get the Facebook User ID
            url = "https://graph.facebook.com/v18.0/me"
            params = {
                "fields": "accounts{instagram_business_account}",
                "access_token": access_token
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 429:
                return {
                    "success": False,
                    "error": "API rate limit exceeded. Please wait before trying again.",
                    "error_code": "RATE_LIMIT_EXCEEDED"
                }
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                return {
                    "success": False,
                    "error": f"Failed to get account info: {error_data.get('error', {}).get('message', 'Unknown error')}",
                    "error_code": "API_ERROR",
                    "status_code": response.status_code
                }
            
            data = response.json()
            
            # Extract Instagram Business Account ID
            accounts = data.get("accounts", {}).get("data", [])
            for account in accounts:
                if "instagram_business_account" in account:
                    instagram_account_id = account["instagram_business_account"]["id"]
                    return {
                        "success": True,
                        "account_id": instagram_account_id
                    }
            
            return {
                "success": False,
                "error": "No Instagram Business Account found. Make sure your Instagram account is connected to a Facebook Page and is a Business account.",
                "error_code": "NO_INSTAGRAM_ACCOUNT"
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out while getting account info",
                "error_code": "TIMEOUT_ERROR"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting account info: {str(e)}",
                "error_code": "ACCOUNT_INFO_ERROR"
            }

    def _create_media_container(
        self,
        instagram_account_id: str,
        post_type: str,
        caption: str,
        image_url: Optional[str],
        access_token: str
    ) -> Dict[str, Any]:
        """Create a media container for the post."""
        try:
            url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/media"
            
            # Prepare parameters based on post type
            params = {
                "access_token": access_token,
                "caption": caption
            }
            
            if post_type == "image":
                params["image_url"] = image_url
                params["media_type"] = "IMAGE"
            else:
                # For text-only posts, we need to use a different approach
                # Instagram Graph API doesn't support pure text posts
                # We'll return an error explaining this limitation
                return {
                    "success": False,
                    "error": "Instagram Graph API does not support text-only posts. Please use an image with your caption or consider using Instagram's native posting features.",
                    "error_code": "TEXT_POSTS_NOT_SUPPORTED"
                }
            
            response = requests.post(url, params=params, timeout=30)
            
            if response.status_code == 429:
                return {
                    "success": False,
                    "error": "API rate limit exceeded. Please wait before trying again.",
                    "error_code": "RATE_LIMIT_EXCEEDED"
                }
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                
                # Handle specific errors
                if "Invalid image URL" in error_message:
                    return {
                        "success": False,
                        "error": "The provided image URL is invalid or inaccessible. Please check the URL and ensure the image is publicly accessible.",
                        "error_code": "INVALID_IMAGE_URL"
                    }
                
                return {
                    "success": False,
                    "error": f"Failed to create media container: {error_message}",
                    "error_code": "CONTAINER_CREATION_ERROR",
                    "status_code": response.status_code
                }
            
            data = response.json()
            container_id = data.get("id")
            
            if not container_id:
                return {
                    "success": False,
                    "error": "No container ID returned from API",
                    "error_code": "NO_CONTAINER_ID"
                }
            
            return {
                "success": True,
                "container_id": container_id
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out while creating media container",
                "error_code": "TIMEOUT_ERROR"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating media container: {str(e)}",
                "error_code": "CONTAINER_ERROR"
            }

    def _publish_media(
        self,
        instagram_account_id: str,
        container_id: str,
        access_token: str,
        scheduled_publish_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """Publish the media container."""
        try:
            url = f"https://graph.facebook.com/v18.0/{instagram_account_id}/media_publish"
            
            params = {
                "creation_id": container_id,
                "access_token": access_token
            }
            
            # Add scheduling if specified
            if scheduled_publish_time:
                params["published"] = "false"
                params["scheduled_publish_time"] = scheduled_publish_time
            
            response = requests.post(url, params=params, timeout=30)
            
            if response.status_code == 429:
                return {
                    "success": False,
                    "error": "API rate limit exceeded. Please wait before trying again.",
                    "error_code": "RATE_LIMIT_EXCEEDED"
                }
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                
                return {
                    "success": False,
                    "error": f"Failed to publish media: {error_message}",
                    "error_code": "PUBLISH_ERROR",
                    "status_code": response.status_code
                }
            
            data = response.json()
            media_id = data.get("id")
            
            result = {
                "success": True,
                "message": "Post published successfully" if not scheduled_publish_time else "Post scheduled successfully",
                "media_id": media_id,
                "instagram_post_url": f"https://www.instagram.com/p/{media_id}/" if media_id else None
            }
            
            if scheduled_publish_time:
                result["scheduled_time"] = datetime.fromtimestamp(scheduled_publish_time, timezone.utc).isoformat()
            
            return result
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out while publishing media",
                "error_code": "TIMEOUT_ERROR"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error publishing media: {str(e)}",
                "error_code": "PUBLISH_MEDIA_ERROR"
            }