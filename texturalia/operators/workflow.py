import bpy
import os
import json
from ..utils.workflow_parser import WorkflowParser

class TEXTURALIA_OT_load_workflow(bpy.types.Operator):
    """Load the selected workflow and generate UI parameters"""
    bl_idname = "texturalia.load_workflow"
    bl_label = "Load Workflow"
    
    def execute(self, context):
        wf = context.scene.texturalia_workflow
        
        # Determine Path
        # If workflow_file is set (Custom), use it.
        # If not, use workflow_name (Enum) from resources.
        
        print(f"Texturalia Debug: workflow_name = '{wf.workflow_name}'")
        
        # Priority:
        # 1. Custom File Path (if set)
        # 2. Enum Selection (if valid)
        
        filepath = ""
        
        if wf.workflow_file and os.path.exists(wf.workflow_file):
             filepath = wf.workflow_file
             print(f"Texturalia Debug: Using custom file = '{filepath}'")
        elif wf.workflow_name and wf.workflow_name != "NONE":
            addon_dir = os.path.dirname(os.path.dirname(__file__)) # Up one level from operators
            filepath = os.path.join(addon_dir, "resources", "workflows", wf.workflow_name)
            print(f"Texturalia Debug: Using enum file = '{filepath}'")
        
        if not filepath or not os.path.exists(filepath):
            self.report({'ERROR'}, f"Workflow file not found: {filepath}")
            return {'CANCELLED'}
            
        # Parse
        data = WorkflowParser.load_workflow(filepath)
        if not data:
            self.report({'ERROR'}, "Failed to parse JSON")
            return {'CANCELLED'}
            
        if not WorkflowParser.validate_workflow(data):
            self.report({'ERROR'}, "Invalid API Workflow format")
            return {'CANCELLED'}
            
        # Clear existing
        wf.node_params.clear()
        wf.cached_json = json.dumps(data)
        
        # Parse Params
        params, nodes_info = WorkflowParser.parse_params(data)
        
        for p in params:
            item = wf.node_params.add()
            item.node_id = p['node_id']
            item.node_title = p['node_title']
            item.param_name = p['param_name']
            item.value_type = p['type']
            
            # Simple grouping by node title
            item.node_group = p['node_title']
            
            # Set Default
            val = p['default']
            if p['type'] == 'INT':
                int_val = int(val)
                # Check Blender IntProperty limits (signed 32-bit)
                if -2147483647 <= int_val <= 2147483647:
                    item.int_val = int_val
                else:
                    # Overflow: Store as String
                    item.value_type = 'STRING' # Override type to force UI to use String field
                    item.str_val = str(val)
                    print(f"Texturalia: Large INT detected ({val}), using STRING")
                    
            elif p['type'] == 'FLOAT':
                item.float_val = float(val)
            elif p['type'] == 'FLOAT_FACTOR':
                item.float_factor = float(val)
            elif p['type'] == 'STRING':
                item.str_val = str(val)
            elif p['type'] == 'BOOL':
                item.bool_val = bool(val)
            elif p['type'] == 'IMAGE':
                # Smart Default for Masks
                if 'mask' in item.node_title.lower():
                    item.image_source = 'VIEW_MASK'
                else:
                    item.image_source = 'VIEW_COLOR'
                
        # Smart Connect (Find Inputs/Outputs)
        inputs, outputs = WorkflowParser.find_special_nodes(data)
        if inputs:
            wf.input_node_id = inputs[0][0] # Pick first candidate
            print(f"Texturalia: Auto-detected Input Node: {inputs[0][1]} ({inputs[0][0]})")
        else:
            wf.input_node_id = ""
            
        if outputs:
            wf.output_node_id = outputs[0][0]
            print(f"Texturalia: Auto-detected Output Node: {outputs[0][1]} ({outputs[0][0]})")
        else:
            wf.output_node_id = ""
            
        self.report({'INFO'}, f"Loaded {len(wf.node_params)} parameters.")
        return {'FINISHED'}
