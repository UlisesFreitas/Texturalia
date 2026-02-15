import json
import os
import bpy

class WorkflowParser:
    """Parses ComfyUI API Workflows (JSON) for Texturalia"""
    
    @staticmethod
    def load_workflow(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                workflow = json.load(f)
            return workflow
        except Exception as e:
            print(f"Texturalia: Failed to load workflow {filepath}: {e}")
            return None

    @staticmethod
    def validate_workflow(workflow):
        if not isinstance(workflow, dict):
            return False
        # Check for at least one node with class_type
        for k, v in workflow.items():
            if "class_type" in v and "inputs" in v:
                return True
        return False

    @staticmethod
    def parse_params(workflow):
        """Extract exposed parameters from the workflow"""
        params = []
        nodes_info = [] # For UI grouping
        
        blacklist_titles = ["Preview 3D", "Preview 3D & Animation", "Animation", "Display"]
        
        for node_id, node_data in workflow.items():
            class_type = node_data.get("class_type", "")
            meta = node_data.get("_meta", {})
            title = meta.get("title", class_type)
            
            # Skip blacklisted
            if any(x in title for x in blacklist_titles):
                continue
                
            # Node Info for UI
            nodes_info.append({
                "id": node_id,
                "title": title,
                "class_type": class_type
            })
            
            inputs = node_data.get("inputs", {})
            for param_name, param_val in inputs.items():
                # Skip links (lists)
                if isinstance(param_val, list):
                    continue
                    
                param_type = None
                default_val = param_val
                
                # Heuristics for type
                if isinstance(param_val, bool):
                    param_type = 'BOOL'
                elif isinstance(param_val, int):
                    param_type = 'INT'
                elif isinstance(param_val, float):
                    param_type = 'FLOAT'
                    # Check for 0-1 Factor Types
                    if param_name in ['denoise', 'strength', 'guidance_start', 'guidance_end', 'start_percent', 'end_percent']:
                        param_type = 'FLOAT_FACTOR'
                elif isinstance(param_val, str):
                    param_type = 'STRING'
                    # Check if it's an image input
                    if param_name in ['image', 'filename', 'image_path']:
                        param_type = 'IMAGE'
                
                if param_type:
                    params.append({
                        "node_id": node_id,
                        "node_title": title,
                        "param_name": param_name,
                        "type": param_type,
                        "default": default_val
                    })
                    
        return params, nodes_info

    @staticmethod
    def find_special_nodes(workflow):
        """Identify potential Input (LoadImage) and Output (SaveImage) nodes"""
        inputs = []
        outputs = []
        
        for node_id, node_data in workflow.items():
            class_type = node_data.get("class_type", "").lower()
            title = node_data.get("_meta", {}).get("title", "").lower()
            
            # Input Candidates
            if "loadimage" in class_type or "load image" in title:
                inputs.append((node_id, title))
            
            # Output Candidates
            if "saveimage" in class_type or "previewimage" in class_type:
                outputs.append((node_id, title))
                
        return inputs, outputs
