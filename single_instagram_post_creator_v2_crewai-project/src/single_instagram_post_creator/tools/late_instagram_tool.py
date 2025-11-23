from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Optional, Dict, Any
import requests
import json
import time
import os
from datetime import datetime, timezone

class LateInstagramRequest(BaseModel):
    """Input schema for Late Instagram Tool."""
    account_id: Optional[str] = Field(
        None, 
        description="Late Instagram account ID to post to. If not provided, will use the default from environment variables."
    )
    content: str = Field(
        ..., 
        description="Post caption/text content for the Instagram post"
    )
    media_urls: Optional[List[str]] = Field(
        default=None, 
        description="List of image URLs for the post. Leave empty for text-only posts."
    )
    schedule_time: Optional[str] = Field(
        default=None, 
        description="ISO format datetime for scheduling (e.g., '2024-12-25T10:30:00Z'). Leave empty for immediate posting."
    )
    post_type: str = Field(
        default="feed", 
        description="Type of Instagram post: 'feed' for regular posts, 'story' for stories, or 'reel' for video reels"
    )
    hashtags: Optional[List[str]] = Field(
        default=None, 
        description="List of hashtags without the # symbol (e.g., ['travel', 'photography'])"
    )
    mentions: Optional[List[str]] = Field(
        default=None, 
        description="List of usernames to mention without the @ symbol (e.g., ['username1', 'username2'])"
    )

class LateInstagramTool(BaseTool):
    """Improved tool for posting and scheduling Instagram content via Late API."""

    name: str = "late_instagram_tool"
    description: str = (
        "An improved and reliable tool for posting and scheduling Instagram content via Late API (getlate.io). "
        "Features enhanced error handling, proper API endpoint usage, simplified functionality for better reliability, "
        "and clear success/failure feedback with debugging information."
    )
    args_schema: Type[BaseModel] = LateInstagramRequest

    def _check_environment_variables(self) -> Dict[str, Any]:
        """Check and validate required environment variables."""
        api_key = os.getenv("LATE_API_KEY")
        account_id = os.getenv("LATE_ACCOUNT_ID")
        
        debug_info = {
            "api_key_found": bool(api_key),
            "account_id_found": bool(account_id),
            "api_key_length": len(api_key) if api_key else 0
        }
        
        if not api_key:
            return {
                "success": False,
                "error_message": "LATE_API_KEY environment variable is not set or empty. Please set your Late API key.",
                "debug_info": debug_info,
                "troubleshooting": "1. Check your environment variables, 2. Ensure LATE_API_KEY is correctly set, 3. Verify API key is not expired"
            }
        
        if len(api_key.strip()) < 10:
            return {
                "success": False,
                "error_message": "LATE_API_KEY appears to be invalid (too short). Please check your API key.",
                "debug_info": debug_info,
                "troubleshooting": "1. Verify API key is complete, 2. Check for extra spaces, 3. Get a new API key from Late.io dashboard"
            }
            
        return {
            "success": True,
            "api_key": api_key,
            "default_account_id": account_id,
            "debug_info": debug_info
        }

    def _validate_inputs(self, post_type: str, content: str, media_urls: Optional[List[str]]) -> Dict[str, Any]:
        """Validate input parameters with detailed error messages."""
        if post_type not in ['feed', 'story', 'reel']:
            return {
                "success": False,
                "error_message": f"Invalid post_type '{post_type}'. Must be 'feed', 'story', or 'reel'.",
                "troubleshooting": "Use 'feed' for regular posts, 'story' for Instagram stories, or 'reel' for video content"
            }
        
        if not content or not content.strip():
            return {
                "success": False,
                "error_message": "Content cannot be empty. Please provide caption text for your post.",
                "troubleshooting": "Add at least a brief caption or description for your Instagram post"
            }
        
        if len(content) > 2200:
            return {
                "success": False,
                "error_message": f"Content is too long ({len(content)} characters). Instagram captions should be under 2200 characters.",
                "troubleshooting": "Shorten your caption or split into multiple posts"
            }
        
        if media_urls and len(media_urls) > 10:
            return {
                "success": False,
                "error_message": f"Too many media URLs ({len(media_urls)}). Instagram allows maximum 10 images per post.",
                "troubleshooting": "Reduce the number of images to 10 or fewer"
            }
        
        return {"success": True}

    def _format_content(self, content: str, hashtags: Optional[List[str]], mentions: Optional[List[str]]) -> str:
        """Format content with hashtags and mentions."""
        formatted_content = content.strip()
        
        # Add mentions (ensure they're not already in the content)
        if mentions:
            for mention in mentions:
                mention_tag = f"@{mention}"
                if mention_tag not in formatted_content:
                    formatted_content += f" {mention_tag}"
        
        # Add hashtags (ensure they're not already in the content)
        if hashtags:
            hashtag_list = []
            for tag in hashtags:
                hashtag = f"#{tag}"
                if hashtag not in formatted_content:
                    hashtag_list.append(hashtag)
            
            if hashtag_list:
                formatted_content += f"\n\n{' '.join(hashtag_list)}"
        
        return formatted_content

    def _make_api_request(self, method: str, endpoint: str, data: Dict[str, Any] = None, api_key: str = "") -> Dict[str, Any]:
        """Make API request with improved error handling."""
        # Use correct Late.io API base URL
        base_url = "https://api.getlate.io"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "CrewAI-LateInstagramTool/1.0"
        }
        
        full_url = f"{base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(full_url, headers=headers, timeout=30)
            else:
                response = requests.post(full_url, headers=headers, json=data, timeout=30)
            
            # Detailed error handling based on status codes
            if response.status_code == 401:
                return {
                    "success": False,
                    "error_message": "Authentication failed. Your API key may be invalid or expired.",
                    "status_code": response.status_code,
                    "troubleshooting": "1. Check your LATE_API_KEY, 2. Verify it's not expired, 3. Generate a new key from Late.io dashboard"
                }
            
            elif response.status_code == 403:
                return {
                    "success": False,
                    "error_message": "Access forbidden. Your account may not have permission for this action.",
                    "status_code": response.status_code,
                    "troubleshooting": "1. Check your Late.io subscription, 2. Verify Instagram account is properly connected, 3. Check account permissions"
                }
            
            elif response.status_code == 429:
                return {
                    "success": False,
                    "error_message": "Rate limit exceeded. Too many requests made recently.",
                    "status_code": response.status_code,
                    "troubleshooting": "Wait a few minutes before trying again, or upgrade your Late.io plan for higher limits"
                }
            
            elif response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_data.get('error', 'Unknown API error'))
                except:
                    error_msg = f"HTTP {response.status_code} error"
                
                return {
                    "success": False,
                    "error_message": f"API Error: {error_msg}",
                    "status_code": response.status_code,
                    "raw_response": response.text[:500] if response.text else "",
                    "troubleshooting": "Check the error details above and verify your request parameters"
                }
            
            # Success - parse response
            try:
                response_data = response.json() if response.text else {}
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            return {
                "success": True,
                "data": response_data,
                "status_code": response.status_code
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error_message": "Request timed out. Late.io API may be slow or unreachable.",
                "troubleshooting": "1. Check your internet connection, 2. Try again in a few minutes, 3. Check Late.io status page"
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error_message": "Connection error. Cannot reach Late.io API.",
                "troubleshooting": "1. Check your internet connection, 2. Verify Late.io service status, 3. Check firewall settings"
            }
        except Exception as e:
            return {
                "success": False,
                "error_message": f"Unexpected error: {str(e)}",
                "troubleshooting": "This is an unexpected error. Please try again or contact support."
            }

    def _validate_schedule_time(self, schedule_time: str) -> Dict[str, Any]:
        """Validate and parse schedule time."""
        if not schedule_time:
            return {"success": True, "is_scheduled": False}
            
        try:
            # Parse the datetime
            if schedule_time.endswith('Z'):
                dt = datetime.fromisoformat(schedule_time[:-1] + '+00:00')
            else:
                dt = datetime.fromisoformat(schedule_time)
            
            # Check if time is in the future
            now = datetime.now(timezone.utc)
            if dt <= now:
                return {
                    "success": False,
                    "error_message": f"Schedule time must be in the future. Provided time: {schedule_time}, Current time: {now.isoformat()}",
                    "troubleshooting": "Use a future date/time for scheduling"
                }
            
            # Check if time is not too far in the future (Late.io may have limits)
            max_days = 365  # 1 year limit
            if (dt - now).days > max_days:
                return {
                    "success": False,
                    "error_message": f"Schedule time is too far in the future (max {max_days} days)",
                    "troubleshooting": "Choose a date within the next year"
                }
            
            return {
                "success": True,
                "is_scheduled": True,
                "parsed_time": dt,
                "formatted_time": dt.isoformat()
            }
            
        except ValueError as e:
            return {
                "success": False,
                "error_message": f"Invalid schedule time format: {str(e)}",
                "troubleshooting": "Use ISO format like '2024-12-25T10:30:00Z' or '2024-12-25T10:30:00'"
            }

    def _run(
        self,
        account_id: Optional[str] = None,
        content: str = "",
        media_urls: Optional[List[str]] = None,
        schedule_time: Optional[str] = None,
        post_type: str = "feed",
        hashtags: Optional[List[str]] = None,
        mentions: Optional[List[str]] = None
    ) -> str:
        """Execute the Late Instagram posting tool with improved reliability."""
        
        try:
            # Check environment variables first
            env_check = self._check_environment_variables()
            if not env_check["success"]:
                return json.dumps(env_check, indent=2)
            
            api_key = env_check["api_key"]
            default_account_id = env_check.get("default_account_id")
            
            # Determine account ID to use
            final_account_id = account_id or default_account_id
            if not final_account_id:
                return json.dumps({
                    "success": False,
                    "error_message": "No account ID provided. Set LATE_ACCOUNT_ID environment variable or provide account_id parameter.",
                    "debug_info": env_check["debug_info"],
                    "troubleshooting": "1. Set LATE_ACCOUNT_ID in environment, 2. Or provide account_id parameter, 3. Get account ID from Late.io dashboard"
                }, indent=2)
            
            # Validate inputs
            validation = self._validate_inputs(post_type, content, media_urls)
            if not validation["success"]:
                return json.dumps(validation, indent=2)
            
            # Validate schedule time
            time_validation = self._validate_schedule_time(schedule_time)
            if not time_validation["success"]:
                return json.dumps(time_validation, indent=2)
            
            is_scheduled = time_validation.get("is_scheduled", False)
            
            # Format content with hashtags and mentions
            formatted_content = self._format_content(content, hashtags, mentions)
            
            # Prepare post data for Late.io API
            post_data = {
                "text": formatted_content,
                "platforms": {
                    "instagram": {
                        "account_id": final_account_id
                    }
                }
            }
            
            # Add media if provided
            if media_urls:
                post_data["media"] = [{"url": url} for url in media_urls]
            
            # Add scheduling if provided
            if is_scheduled:
                post_data["publish_at"] = time_validation["formatted_time"]
            
            # Choose correct endpoint
            if is_scheduled:
                endpoint = "/v1/posts"  # Late.io uses the same endpoint for immediate and scheduled posts
            else:
                endpoint = "/v1/posts"
            
            # Make the API request
            result = self._make_api_request("POST", endpoint, post_data, api_key)
            
            if not result["success"]:
                return json.dumps(result, indent=2)
            
            # Parse successful response
            response_data = result["data"]
            post_id = response_data.get("id", "unknown")
            status = "scheduled" if is_scheduled else "published"
            
            # Create detailed success response
            success_response = {
                "success": True,
                "message": f"Instagram post {status} successfully!",
                "post_details": {
                    "post_id": post_id,
                    "account_id": final_account_id,
                    "status": status,
                    "content_preview": formatted_content[:100] + "..." if len(formatted_content) > 100 else formatted_content,
                    "media_count": len(media_urls) if media_urls else 0,
                    "scheduled_for": time_validation.get("formatted_time") if is_scheduled else None,
                    "post_type": post_type
                },
                "api_response": {
                    "late_post_id": post_id,
                    "full_response": response_data
                },
                "debug_info": {
                    "api_endpoint_used": endpoint,
                    "request_timestamp": datetime.now(timezone.utc).isoformat(),
                    "environment_check": env_check["debug_info"]
                }
            }
            
            return json.dumps(success_response, indent=2)
            
        except Exception as e:
            error_response = {
                "success": False,
                "error_message": f"Unexpected error in tool execution: {str(e)}",
                "error_type": type(e).__name__,
                "troubleshooting": "This is an internal error. Please check your inputs and try again.",
                "debug_info": {
                    "error_occurred_at": datetime.now(timezone.utc).isoformat(),
                    "inputs_received": {
                        "account_id": account_id,
                        "content_length": len(content) if content else 0,
                        "media_count": len(media_urls) if media_urls else 0,
                        "has_schedule": bool(schedule_time),
                        "post_type": post_type
                    }
                }
            }
            return json.dumps(error_response, indent=2)