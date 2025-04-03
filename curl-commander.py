from burp import IBurpExtender, IContextMenuFactory, IExtensionStateListener
from java.util import ArrayList
from javax.swing import JMenuItem
from java.awt.event import ActionListener
from java.awt.datatransfer import DataFlavor
from java.awt.Toolkit import getDefaultToolkit
from java.net import URL
from java.util.concurrent import Executors, ExecutorService
import re
import traceback

# TODO: Add support for more curl options
# Tested on Burp 2025.1 + versions

class BurpExtender(IBurpExtender, IContextMenuFactory, IExtensionStateListener):
    
    def registerExtenderCallbacks(self, callbacks):
        # Store references we'll need later
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        
        # Name our extension
        callbacks.setExtensionName("CURL-Commander")
        
        # Create a thread pool - 2 threads should be enough for this
        self._executorService = Executors.newFixedThreadPool(2)
        
        # Register our stuff
        callbacks.registerContextMenuFactory(self)
        callbacks.registerExtensionStateListener(self)
        
        stdout = callbacks.getStdout()
        print >> stdout, "=== CURL Commander loaded ==="
        print >> stdout, "Right-click anywhere to convert clipboard CURL to Repeater"
    
    def createMenuItems(self, invocation):
        menuList = ArrayList()
        
        # Just one menu item for now, might add more later if needed
        menuItem = JMenuItem("Send CURL to Repeater")
        menuItem.addActionListener(
            ClipboardCurlHandler(self._callbacks, self._helpers, self._executorService)
        )
        menuList.add(menuItem)
        
        return menuList
    
    def extensionUnloaded(self):
        # Clean up our thread pool 
        if self._executorService and not self._executorService.isShutdown():
            self._executorService.shutdown()
            print >> self._callbacks.getStdout(), "CURL Commander: Shutting down thread pool"


class ClipboardCurlHandler(ActionListener):
    
    def __init__(self, callbacks, helpers, executorService):
        self._callbacks = callbacks
        self._helpers = helpers
        self._executorService = executorService
    
    def actionPerformed(self, event):
        # Don't block the UI thread, do the work in background
        self._executorService.submit(lambda: self._processClipboard())
    
    def _processClipboard(self):
        try:
            # Get the clipboard content
            clipboard_stuff = self._getClipboardContent()
            if not clipboard_stuff:
                print >> self._callbacks.getStdout(), "No text in clipboard :("
                return
            
            # Try to parse the CURL command
            curl_data, err = self._parseCurlCommand(clipboard_stuff)
            if err:
                print >> self._callbacks.getStdout(), "Error: " + err
                return
            
            # Extract the necessary bits
            url = curl_data["url"]
            method = curl_data["method"]
            headers = curl_data["headers"]
            body = curl_data["body"]
            
            # Make sure URL has protocol
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url  # Default to HTTPS these days
                print >> self._callbacks.getStdout(), "Added https:// to URL: " + url
            
            # Create URL object - will throw if invalid
            try:
                java_url = URL(url)
            except Exception as e:
                print >> self._callbacks.getStdout(), "Invalid URL: " + str(e)
                return
            
            # Build the request headers
            req_headers = ArrayList()
            
            # Request line first
            path = java_url.getPath() or "/"
            query = java_url.getQuery()
            req_line = method + " " + path
            if query:
                req_line += "?" + query
            req_line += " HTTP/1.1"
            req_headers.add(req_line)
            
            port = java_url.getPort()
            if port != -1 and port != 80 and port != 443:
                req_headers.add("Host: " + java_url.getHost() + ":" + str(port))
            else:
                req_headers.add("Host: " + java_url.getHost())
            
            for hname, hval in headers.items():
                req_headers.add(hname + ": " + hval)
            
            # Build the HTTP message
            if body:
                request = self._helpers.buildHttpMessage(req_headers, self._helpers.stringToBytes(body))
            else:
                request = self._helpers.buildHttpMessage(req_headers, None)
            
            # Figure out the port, defaulting appropriately
            port = java_url.getPort()
            if port == -1:
                # Default ports based on protocol
                port = 443 if java_url.getProtocol() == "https" else 80
            
            # Create a reasonable tab name (truncate if too long)
            path_display = java_url.getPath()
            if len(path_display) > 20:
                path_display = path_display[:20] + "..."
            tab_name = path_display
            
            # Send to repeater!
            self._callbacks.sendToRepeater(
                java_url.getHost(),
                port,
                java_url.getProtocol() == "https",
                request,
                tab_name
            )
            
            # Log what we did
            stdout = self._callbacks.getStdout()
            print >> stdout, "Sent to Repeater: " + url
            print >> stdout, "Method: " + method
            print >> stdout, "Headers: " + str(len(headers))
            if body:
                # Don't log huge bodies
                body_preview = body[:50] + "..." if len(body) > 50 else body
                print >> stdout, "Body: " + body_preview
            else:
                print >> stdout, "Body: None"
            
        except Exception as e:
            print >> self._callbacks.getStdout(), "Error processing request. Check error log"
            self._callbacks.printError("CURL to Repeater error: " + str(e))
            # Print stack trace to help debugging
            trace = traceback.format_exc()
            self._callbacks.printError(trace)
    
    def _getClipboardContent(self):
        # Grab text from clipboard
        try:
            clipboard = getDefaultToolkit().getSystemClipboard()
            if clipboard.isDataFlavorAvailable(DataFlavor.stringFlavor):
                return clipboard.getData(DataFlavor.stringFlavor)
        except Exception:
            print >> self._callbacks.getStderr(), "Failed to access clipboard"
            return None
        return None
    
    def _parseCurlCommand(self, curl_command):
        # This is tricky because curl has so many options and formats!
        try:
            # Handle multiline curl commands
            curl_command = curl_command.replace("\\\n", " ")
            curl_command = curl_command.replace("\\\r\n", " ")
            
            # Basic check - is this even curl?
            if not curl_command.strip().lower().startswith("curl "):
                return None, "Not a curl command"
                
            print >> self._callbacks.getStdout(), "Parsing CURL (first 100 chars): " + curl_command[:100] + "..."
            
            # Extract URL - try a few different patterns
            url_match = None
            
            # Try with --location flag
            url_match = re.search(r'curl\s+(?:--location|-L)\s+[\'"]?(https?://[^\'"\s]+|[^\'"\s]+)[\'"]?', curl_command)
            
            # Try with explicit method
            if not url_match:
                url_match = re.search(r'curl\s+(?:-X|--request)\s+[A-Z]+\s+[\'"]?(https?://[^\'"\s]+|[^\'"\s]+)[\'"]?', curl_command)
            
            # Try bare curl command
            if not url_match:
                url_match = re.search(r'curl\s+[\'"]?(https?://[^\'"\s]+|[^\'"\s]+)[\'"]?', curl_command)
            
            # Last ditch - just look for any URL
            if not url_match:
                url_match = re.search(r'https?://[^\'"\s]+|[^\'"\s]+\.[^\'"\s]+/[^\'"\s]*', curl_command)
            
            if not url_match:
                return None, "Couldn't find URL in curl command"
            
            # Extract URL from the match
            url = url_match.group(1) if hasattr(url_match, 'group') and url_match.group(1) else url_match.group(0)
            
            # Clean up URL
            url = url.strip('\'"')
            if ' ' in url:  # Sometimes we get extra stuff
                url = url.split(' ')[0]
            
            # Default to HTTPS if no protocol
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            
            # Get the HTTP method - default to GET
            method_match = re.search(r'(?:--request|-X)\s+([A-Z]+)', curl_command)
            if not method_match:
                # Try quoted version
                method_match = re.search(r'(?:--request|-X)\s+[\'"]([A-Z]+)[\'"]', curl_command)
            
            method = "GET"  # Default
            if method_match:
                method = method_match.group(1)
            
            print >> self._callbacks.getStdout(), "Found method: " + method
            
            # Extract headers
            headers = {}
            header_matches = re.finditer(r'(?:--header|-H)\s+[\'"]([^:]+):\s*([^\'"]+)[\'"]', curl_command)
            for match in header_matches:
                headers[match.group(1)] = match.group(2)
            
            # Extract body data if present - try various patterns
            body = None
            body_patterns = [
                # JSON objects
                r'(?:--data|-d)\s+\'(\{.+?\})\'',  
                r'(?:--data|-d)\s+"(\{.+?\})"',
                r'(?:--data-raw)\s+\'(\{.+?\})\'',
                r'(?:--data-raw)\s+"(\{.+?\})"',
                # Any data
                r'(?:--data|-d)\s+\'(.+?)\'',
                r'(?:--data|-d)\s+"(.+?)"'
            ]
            
            for pattern in body_patterns:
                body_match = re.search(pattern, curl_command, re.DOTALL)
                if body_match:
                    body = body_match.group(1)
                    break
            
            return {
                "url": url,
                "method": method,
                "headers": headers,
                "body": body
            }, None
        
        except Exception as e:
            # Log the error
            print >> self._callbacks.getStderr(), "Couldn't parse CURL: " + str(e)
            return None, "Failed to parse curl command"
