
import urllib.request
import urllib.parse
import json
import time

class ComfyClient:
    def __init__(self, server_url="http://127.0.0.1:8188"):
        self.server_url = server_url.rstrip('/')

    def is_connected(self):
        """Check if ComfyUI server is reachable"""
        try:
            with urllib.request.urlopen(f"{self.server_url}/system_stats", timeout=2) as response:
                return response.status == 200
        except:
            return False

    def queue_prompt(self, workflow_json):
        """Send a workflow to the prompt queue"""
        p = {"prompt": workflow_json}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"{self.server_url}/prompt", data=data)
        
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read())
        except Exception as e:
            print(f"ComfyUI Queue Error: {e}")
            return None

    def get_history(self, prompt_id):
        """Get history for a specific prompt ID"""
        try:
            with urllib.request.urlopen(f"{self.server_url}/history/{prompt_id}") as response:
                return json.loads(response.read())
        except Exception as e:
            print(f"ComfyUI History Error: {e}")
            return None
    
    def upload_image(self, filepath, subfolder="", overwrite=True):
        """Upload an image to ComfyUI input directory using multipart/form-data"""
        import os
        import mimetypes
        import uuid

        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return None

        filename = os.path.basename(filepath)
        boundary = uuid.uuid4().hex
        
        # Prepare body
        data = []
        
        # File field
        data.append(f'--{boundary}')
        data.append(f'Content-Disposition: form-data; name="image"; filename="{filename}"')
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        data.append(f'Content-Type: {content_type}')
        data.append('')
        
        # Read file binary
        with open(filepath, 'rb') as f:
            file_bytes = f.read()
            
        # Context fields
        if subfolder:
            data.append(f'--{boundary}')
            data.append('Content-Disposition: form-data; name="subfolder"')
            data.append('')
            data.append(subfolder)
            
        if overwrite:
            data.append(f'--{boundary}')
            data.append('Content-Disposition: form-data; name="overwrite"')
            data.append('')
            data.append('true')

        # Construct body
        # Note: We need to mix str and bytes, so we'll construct purely in bytes
        body = b''
        for item in data:
            body += item.encode('utf-8') + b'\r\n'
            
        # Add file content (already bytes)
        # Wait, the structure above was slightly wrong for mixing types. 
        # Let's do it cleaner:
        
        body = b''
        
        # 1. Image Header
        body += f'--{boundary}\r\n'.encode('utf-8')
        body += f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode('utf-8')
        body += f'Content-Type: {content_type}\r\n\r\n'.encode('utf-8')
        body += file_bytes + b'\r\n'
        
        # 2. Subfolder
        if subfolder:
            body += f'--{boundary}\r\n'.encode('utf-8')
            body += f'Content-Disposition: form-data; name="subfolder"\r\n\r\n'.encode('utf-8')
            body += f'{subfolder}\r\n'.encode('utf-8')
            
        # 3. Overwrite
        if overwrite:
            body += f'--{boundary}\r\n'.encode('utf-8')
            body += f'Content-Disposition: form-data; name="overwrite"\r\n\r\n'.encode('utf-8')
            body += b'true\r\n'
            
        # Final boundary
        body += f'--{boundary}--\r\n'.encode('utf-8')
        
        # Request
        req = urllib.request.Request(f"{self.server_url}/upload/image", data=body)
        req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
        
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read())
        except Exception as e:
            print(f"ComfyUI Upload Error: {e}")
            return None

    def download_image(self, filename, subfolder="", type="output"):
        """Download an image from ComfyUI"""
        params = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": subfolder,
            "type": type
        })
        
        try:
            with urllib.request.urlopen(f"{self.server_url}/view?{params}") as response:
                return response.read()
        except Exception as e:
            print(f"ComfyUI Download Error: {e}")
            return None

    def get_checkpoint_list(self):
        """Get list of available checkpoints from ComfyUI"""
        try:
            with urllib.request.urlopen(f"{self.server_url}/object_info/CheckpointLoaderSimple", timeout=2) as response:
                data = json.loads(response.read())
                # structure: {'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [['file1', 'file2'], ...]}}}}
                return data.get('CheckpointLoaderSimple', {}).get('input', {}).get('required', {}).get('ckpt_name', [])[0]
        except Exception as e:
            print(f"ComfyUI Checkpoint Fetch Error: {e}")
            return []

    def get_controlnet_list(self):
        """Get list of available ControlNet models from ComfyUI"""
        try:
            with urllib.request.urlopen(f"{self.server_url}/object_info/ControlNetLoader", timeout=2) as response:
                data = json.loads(response.read())
                # structure: {'ControlNetLoader': {'input': {'required': {'control_net_name': [['file1', 'file2'], ...]}}}}
                return data.get('ControlNetLoader', {}).get('input', {}).get('required', {}).get('control_net_name', [])[0]
        except Exception as e:
            print(f"ComfyUI ControlNet Fetch Error: {e}")
            return []
