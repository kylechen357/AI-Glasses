"""
Task Executor for Remote Host Commands
Executes tasks on remote computers (opening browsers, applications, etc.)
"""

import asyncio
import json
import logging
import subprocess
import os
import base64
from typing import Dict, Any, Optional
from datetime import datetime
import tempfile
import platform

logger = logging.getLogger(__name__)

class TaskExecutor:
    """Executes tasks on the local/remote host"""
    
    def __init__(self):
        self.supported_tasks = {
            "display_stock": self._execute_stock_display,
            "web_search": self._execute_web_search,
            "browser_control": self._execute_browser_control,
            "file_operation": self._execute_file_operation,
            "general_display": self._execute_general_display,
            "show_text": self._execute_show_text
        }
        self.system = platform.system().lower()
        
    async def initialize(self):
        """Initialize task executor"""
        logger.info("Initializing Task Executor...")
        logger.info(f"Operating System: {self.system}")
        logger.info(f"Supported tasks: {list(self.supported_tasks.keys())}")
        
    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task based on task data"""
        task_id = task_data.get("task_id", "unknown")
        task_type = task_data.get("task_type")
        task_params = task_data.get("task_params", {})
        ai_response = task_data.get("ai_response", "")
        
        logger.info(f"Executing task {task_id}: {task_type}")
        
        try:
            if task_type not in self.supported_tasks:
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": f"Unsupported task type: {task_type}",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Execute the task
            result = await self.supported_tasks[task_type](task_params, ai_response)
            
            # Take screenshot after execution
            screenshot = await self._take_screenshot()
            
            return {
                "task_id": task_id,
                "status": "completed",
                "result": result,
                "screenshot": screenshot,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}")
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _execute_stock_display(self, params: Dict[str, Any], ai_response: str) -> str:
        """Display stock information"""
        symbols = params.get("symbols", [])
        
        if symbols:
            # Option 1: Open Yahoo Finance
            symbol = symbols[0]  # Use first symbol
            url = f"https://finance.yahoo.com/quote/{symbol}"
            await self._open_browser(url)
            return f"Opened stock chart for {symbol}"
        else:
            # Option 2: Show AI response in a window
            await self._show_text_window("Stock Information", ai_response)
            return "Displayed stock information"
    
    async def _execute_web_search(self, params: Dict[str, Any], ai_response: str) -> str:
        """Execute web search"""
        search_term = params.get("search_term")
        
        if search_term:
            # Open Google search
            query = search_term.replace(" ", "+")
            url = f"https://www.google.com/search?q={query}"
            await self._open_browser(url)
            return f"Opened Google search for: {search_term}"
        else:
            # Show AI response
            await self._show_text_window("Search Results", ai_response)
            return "Displayed search information"
    
    async def _execute_browser_control(self, params: Dict[str, Any], ai_response: str) -> str:
        """Control browser or open URLs"""
        urls = params.get("urls", [])
        
        if urls:
            # Open the first URL
            url = urls[0]
            await self._open_browser(url)
            return f"Opened URL: {url}"
        else:
            # Extract URL from tool result or AI response
            tool_result = params.get("tool_result", "")
            if "http" in str(tool_result):
                # Try to extract URL from tool result
                import re
                url_match = re.search(r'http[s]?://[^\s<>"]+', str(tool_result))
                if url_match:
                    url = url_match.group()
                    await self._open_browser(url)
                    return f"Opened extracted URL: {url}"
            
            # Show AI response
            await self._show_text_window("Browser Information", ai_response)
            return "Displayed browser-related information"
    
    async def _execute_file_operation(self, params: Dict[str, Any], ai_response: str) -> str:
        """Execute file operations"""
        tool_result = params.get("tool_result", "")
        
        if isinstance(tool_result, dict) and "files" in tool_result:
            # If file listing, open file manager
            await self._open_file_manager()
            return "Opened file manager"
        else:
            # Show file operation result
            await self._show_text_window("File Operation Result", ai_response)
            return "Displayed file operation information"
    
    async def _execute_general_display(self, params: Dict[str, Any], ai_response: str) -> str:
        """Display general AI response"""
        await self._show_text_window("AI Response", ai_response)
        return "Displayed AI response"
    
    async def _execute_show_text(self, params: Dict[str, Any], ai_response: str) -> str:
        """Show text in a window"""
        title = params.get("title", "AI Response")
        text = params.get("text", ai_response)
        await self._show_text_window(title, text)
        return f"Displayed text window: {title}"
    
    async def _open_browser(self, url: str):
        """Open URL in default browser"""
        try:
            if self.system == "linux":
                subprocess.Popen(["xdg-open", url])
            elif self.system == "darwin":  # macOS
                subprocess.Popen(["open", url])
            elif self.system == "windows":
                subprocess.Popen(["start", url], shell=True)
            else:
                logger.warning(f"Unsupported system for browser opening: {self.system}")
                
        except Exception as e:
            logger.error(f"Error opening browser: {e}")
    
    async def _open_file_manager(self):
        """Open file manager"""
        try:
            if self.system == "linux":
                # Try different file managers
                for fm in ["nautilus", "dolphin", "thunar", "pcmanfm"]:
                    try:
                        subprocess.Popen([fm])
                        break
                    except FileNotFoundError:
                        continue
            elif self.system == "darwin":  # macOS
                subprocess.Popen(["open", "."])
            elif self.system == "windows":
                subprocess.Popen(["explorer", "."])
                
        except Exception as e:
            logger.error(f"Error opening file manager: {e}")
    
    async def _show_text_window(self, title: str, text: str):
        """Show text in a window or notification"""
        try:
            # Create a simple HTML file and open it
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{title}</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        max-width: 800px;
                        margin: 50px auto;
                        padding: 20px;
                        background-color: #f5f5f5;
                    }}
                    .container {{
                        background-color: white;
                        padding: 30px;
                        border-radius: 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }}
                    h1 {{
                        color: #333;
                        border-bottom: 2px solid #007bff;
                        padding-bottom: 10px;
                    }}
                    .content {{
                        font-size: 16px;
                        line-height: 1.6;
                        color: #444;
                        white-space: pre-wrap;
                    }}
                    .timestamp {{
                        font-size: 12px;
                        color: #666;
                        margin-top: 20px;
                        text-align: right;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>{title}</h1>
                    <div class="content">{text}</div>
                    <div class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                </div>
            </body>
            </html>
            """
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                f.write(html_content)
                html_file = f.name
            
            # Open in browser
            await self._open_browser(f"file://{html_file}")
            
            # Clean up after delay
            asyncio.create_task(self._cleanup_temp_file(html_file, delay=300))  # 5 minutes
            
        except Exception as e:
            logger.error(f"Error showing text window: {e}")
            # Fallback: try to show notification
            await self._show_notification(title, text[:100] + "..." if len(text) > 100 else text)
    
    async def _show_notification(self, title: str, text: str):
        """Show system notification"""
        try:
            if self.system == "linux":
                subprocess.Popen(["notify-send", title, text])
            elif self.system == "darwin":  # macOS
                script = f'display notification "{text}" with title "{title}"'
                subprocess.Popen(["osascript", "-e", script])
            elif self.system == "windows":
                # Windows notification - requires additional setup
                logger.info(f"NOTIFICATION: {title} - {text}")
                
        except Exception as e:
            logger.error(f"Error showing notification: {e}")
    
    async def _cleanup_temp_file(self, filepath: str, delay: int = 300):
        """Clean up temporary file after delay"""
        await asyncio.sleep(delay)
        try:
            os.unlink(filepath)
        except Exception as e:
            logger.error(f"Error cleaning up temp file: {e}")
    
    async def _take_screenshot(self) -> Optional[str]:
        """Take screenshot and return base64 encoded image"""
        try:
            # Try different screenshot methods based on OS
            if self.system == "linux":
                # Try scrot, gnome-screenshot, or ImageMagick
                for cmd in [
                    ["scrot", "-"],
                    ["gnome-screenshot", "-f", "-"],
                    ["import", "-window", "root", "-"]
                ]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, timeout=10)
                        if result.returncode == 0:
                            return base64.b64encode(result.stdout).decode()
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        continue
                        
            elif self.system == "darwin":  # macOS
                result = subprocess.run(
                    ["screencapture", "-x", "-t", "png", "-"],
                    capture_output=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return base64.b64encode(result.stdout).decode()
                    
            # If no screenshot method worked, return None
            logger.warning("No screenshot method available")
            return None
            
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None

    async def shutdown(self):
        """Shutdown task executor"""
        logger.info("Task Executor shutdown complete")
