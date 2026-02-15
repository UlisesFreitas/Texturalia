import bpy
import os
from .utils.comfy_client import ComfyClient

# Global cache for checkpoints
# Global cache
cached_checkpoints = []
cached_controlnets = []

def refresh_comfy_resources(prefs):
    """Fetch resources from ComfyUI and update globals/prefs"""
    global cached_checkpoints, cached_controlnets
    
    url = prefs.comfy_url or "http://127.0.0.1:8188"
    client = ComfyClient(url)
    
    if not client.is_connected():
        return False, "Could not connect to ComfyUI"
        
    # 1. Fetch Checkpoints
    checkpoints = client.get_checkpoint_list()
    if checkpoints:
        cached_checkpoints = []
        for i, ckpt in enumerate(checkpoints):
            cached_checkpoints.append((ckpt, ckpt, "", "FILE_TICK", i+1))
            
        # Auto-Select Logic
        if cached_checkpoints:
            # If current selection is invalid or 'NONE', select the first one
            current = getattr(prefs, "comfy_checkpoint", "NONE")
            valid_ids = [item[0] for item in cached_checkpoints]
            
            if current not in valid_ids:
                try:
                    prefs.comfy_checkpoint = cached_checkpoints[0][0]
                    print(f"Texturalia: Auto-selected checkpoint: {cached_checkpoints[0][0]}")
                except AttributeError:
                    # Can happen during drawing/read-only context
                    pass
    else:
        cached_checkpoints = []
        
    # 2. Fetch ControlNets
    controlnets = client.get_controlnet_list()
    if controlnets:
        cached_controlnets = []
        for i, cn in enumerate(controlnets):
            cached_controlnets.append((cn, cn, "", "NODE", i+1))
            
        # Auto-Select ControlNets if not set
        if cached_controlnets:
            try:
                # Basic heuristics for Depth
                depths = [cn[0] for cn in cached_controlnets if 'depth' in cn[0].lower()]
                if depths and (not prefs.controlnet_depth_model or prefs.controlnet_depth_model == 'NONE'):
                    prefs.controlnet_depth_model = depths[0]
                
                # Basic heuristics for Normal
                normals = [cn[0] for cn in cached_controlnets if 'normal' in cn[0].lower()]
                if normals and (not prefs.controlnet_normal_model or prefs.controlnet_normal_model == 'NONE'):
                    prefs.controlnet_normal_model = normals[0]
            except AttributeError:
                pass
    else:
        cached_controlnets = []
        
    return True, f"Found {len(checkpoints) if checkpoints else 0} ckpts, {len(controlnets) if controlnets else 0} cnets"

def get_checkpoint_items(self, context):
    try:
        global cached_checkpoints
        # Auto-fetch if empty
        if not cached_checkpoints:
             success, msg = refresh_comfy_resources(self)
             if not success and not cached_checkpoints:
                 return [("NONE", "No Checkpoints (Click Refresh)", "", "ERROR", 0)]
        
        return cached_checkpoints
    except Exception as e:
        print(f"Texturalia Prefs Error: {e}")
        return [("NONE", f"Error: {e}", "", "ERROR", 0)]

def get_controlnet_items(self, context):
    try:
        global cached_controlnets
        if not cached_controlnets:
             # This might have been populated by checkpoint fetch, if not, try once
             refresh_comfy_resources(self)
             
        if not cached_controlnets:
            return [("NONE", "No ControlNets (Click Refresh)", "", "ERROR", 0)]
        return cached_controlnets
    except Exception as e:
        print(f"Texturalia Prefs Error: {e}")
        return [("NONE", f"Error: {e}", "", "ERROR", 0)]

class TEXTURALIA_OT_refresh_checkpoints(bpy.types.Operator):
    """Fetch available checkpoints and ControlNets from ComfyUI"""
    bl_idname = "texturalia.refresh_checkpoints"
    bl_label = "Refresh ComfyUI Resources"
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        success, msg = refresh_comfy_resources(prefs)
        
        if success:
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

class TexturaliaPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    comfy_url: bpy.props.StringProperty(
        name="ComfyUI URL",
        default="http://127.0.0.1:8188",
        description="URL of the ComfyUI server"
    )

    comfy_output_dir: bpy.props.StringProperty(
        name="ComfyUI Output",
        subtype='DIR_PATH',
        default="",
        description="Folder where ComfyUI saves generated images (Optional override)"
    )

    comfy_checkpoint: bpy.props.EnumProperty(
        name="Checkpoint",
        items=get_checkpoint_items,
        description="Select Stable Diffusion Checkpoint"
    )

    texturalia_output_dir: bpy.props.StringProperty(
        name="Texturalia Output",
        subtype='DIR_PATH',
        default="",
        description="Folder to save captured views (Mandatory)"
    )

    # ControlNet Models
    controlnet_depth_model: bpy.props.EnumProperty(
        name="Depth Model",
        items=get_controlnet_items,
        description="Select ControlNet Depth model"
    )
    
    controlnet_normal_model: bpy.props.EnumProperty(
        name="Normal Model",
        items=get_controlnet_items,
        description="Select ControlNet Normal model"
    )

    def draw(self, context):
        print("DEBUG: Drawing Texturalia Preferences")
        layout = self.layout
        
        box = layout.box()
        box.label(text="ComfyUI Settings")
        box.prop(self, "comfy_url")
        
        row = box.row()
        row.prop(self, "comfy_checkpoint")
        row.operator("texturalia.refresh_checkpoints", text="", icon='FILE_REFRESH')
        
        if not cached_checkpoints or cached_checkpoints[0][0] == "NONE":
            box.label(text="No checkpoints? Download SD 1.5:", icon='INFO')
            box.operator("wm.url_open", text="Download v1-5-pruned.ckpt").url = "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"
        
        box.prop(self, "comfy_output_dir")
        box.operator("texturalia.test_connection", text="Test Connection", icon='URL')
        
        # --- ControlNet Settings ---
        box = layout.box()
        box.label(text="ControlNet Settings", icon='NODETREE')
        row = box.row()
        row.prop(self, "controlnet_depth_model")
        row.prop(self, "controlnet_normal_model")
        
        # --- Installation / Resources ---
        box = layout.box()
        box.label(text="Resources & Installation", icon='IMPORT')
        
        col = box.column(align=True)
        # Checkpoints
        col.label(text="Checkpoints:")
        col.operator("wm.url_open", text="Download SD 1.5 (Pruned)", icon='FILE_BLEND').url = "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt"
        col.operator("wm.url_open", text="Download DreamShaper 8", icon='FILE_BLEND').url = "https://civitai.com/api/download/models/128713"

        col.separator()
        
        # ControlNet
        col.label(text="ControlNet (SD 1.5):")
        col.operator("wm.url_open", text="Download Depth Model (.pth)", icon='LINKED').url = "https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_depth.pth"
        col.operator("wm.url_open", text="Download Normal Model (.pth)", icon='LINKED').url = "https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_normalbae.pth"
        
        # Dependency specific to our workflow
        col.separator()
        sub = col.column(align=True)
        sub.label(text="Required for Background Removal:")
        sub.operator("wm.url_open", text="Install 'ComfyUI-Easy-Use' Nodes", icon='PREFERENCES').url = "https://github.com/yolain/ComfyUI-Easy-Use"
        
        box = layout.box()
        box.label(text="Texturalia Settings")
        box.prop(self, "texturalia_output_dir")
