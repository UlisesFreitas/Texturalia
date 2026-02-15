
import json
import random
import bpy
import os
import time
import math
from datetime import datetime
from ..utils.comfy_client import ComfyClient
from ..utils.common import get_prefs

def resolve_path(path):
    """Robust path resolution handling unsaved files and mixed slashes"""
    if not path:
        return ""
        
    # Normalize to forward slashes for easier handling
    s_path = str(path).replace("\\", "/")
    
    # Handle Blender relative paths
    if s_path.startswith("//"):
        if not bpy.data.is_saved:
            # If unsaved, we can't resolve '//'. 
            raise Exception("Please SAVE your blend file to use relative paths.")
            
        # Manual resolution is often safer/clearer than bpy.path.abspath for //
        base_dir = os.path.dirname(bpy.data.filepath)
        # Remove '//'
        rel_path = s_path[2:]
        # Remove leading slash if present (e.g. //\folder -> /folder -> folder)
        if rel_path.startswith("/"):
            rel_path = rel_path[1:]
            
        abs_path = os.path.join(base_dir, rel_path)
    else:
        # Standard resolution
        abs_path = bpy.path.abspath(s_path)
    
    # Normalize OS separators (handles .. bounds too)
    try:
        abs_path = os.path.normpath(abs_path)
    except:
        pass
        
    return abs_path

def save_image_with_history(context, view, raw_bytes):
    """Save raw bytes to a new timestamped file and add to view history"""
    
    # 1. Determine Output Directory
    prefs = get_prefs(context)
    output_dir = ""
    
    # Priority 1: Preferences Output Dir
    if prefs and prefs.texturalia_output_dir:
        try:
            p = resolve_path(prefs.texturalia_output_dir)
            if os.path.exists(p):
                output_dir = p
        except:
            pass
            
    # Priority 2: Current View Image Dir
    if not output_dir and view.image_path:
        try:
            p = resolve_path(view.image_path)
            if os.path.exists(os.path.dirname(p)):
                output_dir = os.path.dirname(p)
        except:
            pass
            
    # Priority 3: Blend File Dir
    if not output_dir:
        if bpy.data.filepath:
            output_dir = os.path.dirname(bpy.data.filepath)
        else:
            raise Exception("Nowhere to save! Please save .blend file or set Output Dir in Prefs.")

    # 2. Generate Filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize view name
    safe_name = "".join([c for c in view.name if c.isalnum() or c in (' ', '_', '-')]).strip()
    filename = f"{safe_name}_{timestamp}.png"
    filepath = os.path.join(output_dir, filename)
    
    # 3. Save to Disk
    with open(filepath, 'wb') as f:
        f.write(raw_bytes)
        
    # 4. Add to History
    item = view.history.add()
    item.name = timestamp
    item.image_path = filepath
    item.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Capture current settings (optional, for Phase 1.5)
    wf_settings = context.scene.texturalia_workflow
    # item.prompt = ... (retrieve from node params?)
    
    # 5. Update Active View
    view.image_path = filepath
    view.history_active_index = len(view.history) - 1
    
    # 6. Update Blender Image Block
    if view.image_ref:
        view.image_ref.filepath = filepath
        view.image_ref.reload()
        view.image_ref.alpha_mode = 'STRAIGHT'
    else:
        # Load new
        try:
            img = bpy.data.images.load(filepath)
            img.name = f"Texturalia_{view.name}"
            img.alpha_mode = 'STRAIGHT'
            view.image_ref = img
        except Exception as e:
            print(f"Failed to load image: {e}")
            
    return filepath
class TEXTURALIA_OT_test_connection(bpy.types.Operator):
    """Test connection to ComfyUI server"""
    bl_idname = "texturalia.test_connection"
    bl_label = "Test Connection"
    
    def execute(self, context):
        prefs = get_prefs(context)
        if not prefs:
            self.report({'ERROR'}, "Could not find Texturalia preferences")
            return {'CANCELLED'}
            
        url = prefs.comfy_url or "http://127.0.0.1:8188"
        
        client = ComfyClient(url)
        if client.is_connected():
            self.report({'INFO'}, f"Connected to ComfyUI at {url}")
        else:
            self.report({'ERROR'}, f"Failed to connect to {url}")
            
        return {'FINISHED'}

def ensure_mask_uploaded(context, view, client, cache=None):
    """
    Captures mask from viewport (handling UVs) and uploads it.
    Returns the uploaded filename.
    """
    # 1. Determine Path
    if view.image_path:
        base_dir = os.path.dirname(resolve_path(view.image_path))
    else:
        base_dir = bpy.app.tempdir
        
    path = os.path.join(base_dir, f"Texturalia_Mask_Temp_{view.name}.png")
    
    # 2. Capture Logic (with UV Handling)
    try:
        # Camera Setup
        from ..utils.common import move_camera_to_view, capture_view_to_file
        move_camera_to_view(context, view)
        
        mesh_obj = context.view_layer.objects.active
        target_uv_name = f"UV_{view.name}"
        original_uv_name = None
        created_transient = False
        
        if mesh_obj and mesh_obj.type == 'MESH':
            # --- ROBUST MASK CAPTURE: ALPHA CLIP TECHNIQUE ---
            
            # 1. PREPARE UVs
            # We prioritize UV_Mask_Project (Painted) > UV_ViewName (Projected) > Existing
            target_uv_name = "UV_Mask_Project"
            original_uv_name = mesh_obj.data.uv_layers.active.name if mesh_obj.data.uv_layers.active else None
            
            if mesh_obj.data.uv_layers.get("UV_Mask_Project"):
                 uv_l = mesh_obj.data.uv_layers["UV_Mask_Project"]
                 uv_l.active = True
                 uv_l.active_render = True
            elif f"UV_{view.name}" in mesh_obj.data.uv_layers:
                 target_uv_name = f"UV_{view.name}"
                 uv_l = mesh_obj.data.uv_layers[target_uv_name]
                 uv_l.active = True
                 uv_l.active_render = True
            else:
                 # Create Transient Logic (Only if no paint UV exists)
                 created_transient = True
                 target_uv_name = f"UV_{view.name}"
                 uv_layer = mesh_obj.data.uv_layers.new(name=target_uv_name)
                 mesh_obj.data.uv_layers.active = uv_layer
                 
                 # Project
                 bpy.ops.object.mode_set(mode='EDIT')
                 bpy.ops.mesh.select_all(action='SELECT')
                 
                 # Force Context Override for Projection
                 for window in context.window_manager.windows:
                    screen = window.screen
                    for area in screen.areas:
                        if area.type == 'VIEW_3D':
                             with context.temp_override(window=window, area=area):
                                  context.scene.camera = bpy.data.objects.get("Texturalia_Camera")
                                  bpy.ops.view3d.view_camera()
                                  bpy.ops.uv.project_from_view(camera_bounds=True, correct_aspect=True, scale_to_bounds=True)
                             break
                 
                 bpy.ops.object.mode_set(mode='OBJECT')

            # 2. MATERIAL OVERRIDE (Alpha Clip)
            original_materials = [s.material for s in mesh_obj.material_slots]
            
            # Find Mask Image
            mask_name = f"Mask_{view.name}"
            mask_img = bpy.data.images.get(mask_name)
            
            if not mask_img:
                # Fallback: Try dot separator (common in some Blender naming cases)
                alt_name = f"Mask.{view.name}"
                mask_img = bpy.data.images.get(alt_name)
            
            if not mask_img:
                print(f"Mask image not found. Tried '{mask_name}' and 'Mask.{view.name}'. Using blank/skipping.")
                return None
            
            # Create Temp Material (Emission)
            temp_mat = bpy.data.materials.new(name="Texturalia_Temp_Mask_Mat")
            temp_mat.use_nodes = True
            temp_mat.blend_method = 'OPAQUE'
            try:
                temp_mat.shadow_method = 'NONE'
            except AttributeError:
                pass
            
            tree = temp_mat.node_tree
            tree.nodes.clear()
            
            emis = tree.nodes.new('ShaderNodeEmission')
            emis.location = (0,0)
            emis.inputs['Strength'].default_value = 1.0
            
            tex = tree.nodes.new('ShaderNodeTexImage')
            tex.location = (-300, 0)
            tex.image = mask_img
            
            out = tree.nodes.new('ShaderNodeOutputMaterial')
            out.location = (300,0)
            
            tree.links.new(tex.outputs['Color'], emis.inputs['Color'])
            tree.links.new(emis.outputs['Emission'], out.inputs['Surface'])
            
            # Apply Material
            mesh_obj.data.materials.clear()
            mesh_obj.data.materials.append(temp_mat)
            
            # 3. CAPTURE
            rs = context.scene.render.image_settings
            orig_fmt = rs.file_format
            orig_mode = rs.color_mode
            
            try:
                rs.file_format = 'PNG'
                rs.color_mode = 'RGBA'
                
                capture_view_to_file(
                context, 
                view, 
                path, 
                engine='BLENDER_EEVEE',
                use_viewport=False
            )
                
                # DEBUG SAVE
                debug_path = os.path.join(base_dir, f"DEBUG_Mask_{view.name}.png")
                import shutil
                try:
                    shutil.copy(path, debug_path)
                    print(f"Saved Debug Mask: {debug_path}")
                except:
                    pass
                    
            finally:
                rs.file_format = orig_fmt
                rs.color_mode = orig_mode
                
                # Restore
                mesh_obj.data.materials.clear()
                for m in original_materials:
                    mesh_obj.data.materials.append(m)
                    
                if original_uv_name and original_uv_name in mesh_obj.data.uv_layers:
                     mesh_obj.data.uv_layers[original_uv_name].active_render = True
                
                if created_transient:
                     uv = mesh_obj.data.uv_layers.get(target_uv_name)
                     if uv: mesh_obj.data.uv_layers.remove(uv)
                     
                bpy.data.materials.remove(temp_mat)
                    
            if original_uv_name and original_uv_name in mesh_obj.data.uv_layers:
                 mesh_obj.data.uv_layers[original_uv_name].active_render = True
                 mesh_obj.data.uv_layers[original_uv_name].active = True

    except Exception as e:
        print(f"Mask Capture Error: {e}")
        import traceback
        traceback.print_exc()
        return None

    # 4. Upload
    if not os.path.exists(path):
        return None
        
    if cache and path in cache:
        return cache[path]
    
    resp = client.upload_image(path, overwrite=True)
    if resp:
        name = resp.get('name')
        if cache is not None:
            cache[path] = name
        return name
    return None

def inject_mask_auto(workflow, mask_filename):
    """
    Finds a suitable node for the mask and injects the filename.
    Prioritizes VAEEncodeForInpaint source or nodes titled 'Mask'.
    """
    target_node_id = None
    
    # 1. Trace VAEEncodeForInpaint
    for nid, node in workflow.items():
        if node.get('class_type') == 'VAEEncodeForInpaint':
            mask_input = node.get('inputs', {}).get('mask')
            if isinstance(mask_input, list) and len(mask_input) == 2:
                source_nid = str(mask_input[0])
                source_node = workflow.get(source_nid)
                if source_node:
                    s_type = source_node.get('class_type')
                    if s_type in ['LoadImage', 'LoadImageMask', 'ImageUpload']:
                        target_node_id = source_nid
                        break
                    elif s_type == 'MaskFromImage': 
                         img_input = source_node.get('inputs', {}).get('image')
                         if isinstance(img_input, list):
                              real_source_nid = str(img_input[0])
                              real_source = workflow.get(real_source_nid)
                              if real_source and real_source.get('class_type') in ['LoadImage', 'LoadImageMask']:
                                   target_node_id = real_source_nid
                                   break
    
    # 2. Fallback: Title Search
    if not target_node_id:
         for nid, node in workflow.items():
              title = node.get('_meta', {}).get('title', '').lower()
              if 'mask' in title and node.get('class_type') in ['LoadImage', 'LoadImageMask']:
                   target_node_id = nid
                   break
    
    # 3. Inject
    if target_node_id:
        print(f"Auto-Injecting Mask to Node {target_node_id}")
        if 'inputs' not in workflow[target_node_id]:
            workflow[target_node_id]['inputs'] = {}
        
        # Determine key (usually 'image' for LoadImage)
        workflow[target_node_id]['inputs']['image'] = mask_filename
        return True
    
    return False


print("DEBUG: Texturalia Comfy Module Loaded")

class TEXTURALIA_OT_enhance_view(bpy.types.Operator):
    """Send current view image to ComfyUI for enhancement"""
    bl_idname = "texturalia.enhance_view"
    bl_label = "Enhance View (AI)"
    bl_description = "Enhance current view using ComfyUI (Img2Img)"
    
    _timer = None
    _client = None
    _prompt_id = None
    _view_name = ""
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            # Poll history
            history = self._client.get_history(self._prompt_id)
            
            if history and self._prompt_id in history:
                # Execution finished
                self.report({'INFO'}, "Enhancement Finished! Downloading result...")
                
                # Get output filename
                outputs = history[self._prompt_id].get('outputs', {})
                # Assuming node "9" is SaveImage as per our json
                # But better to check any output
                images = []
                for node_id, node_output in outputs.items():
                    if 'images' in node_output:
                        images.extend(node_output['images'])
                
                if images:
                    # Download first image
                    img_data = images[0]
                    filename = img_data['filename']
                    subfolder = img_data['subfolder']
                    img_type = img_data['type']
                    
                    raw_bytes = self._client.download_image(filename, subfolder, img_type)
                    
                    if raw_bytes:
                        # Save to disk (overwrite view image or create new?)
                        # Strategy: Overwrite the view's file and reload
                        
                        # Find the view item
                        scene = context.scene
                        view_item = None
                        for v in scene.texturalia_views:
                            if v.name == self._view_name:
                                view_item = v
                                break
                        
                        if view_item and view_item.image_path:
                            # Backup original? Maybe later. For now overwrite.
                            file_path = view_item.image_path
                            
                            # Write new bytes
                            try:
                                with open(file_path, 'wb') as f:
                                    f.write(raw_bytes)
                                
                                # Reload in Blender
                                if view_item.image_ref:
                                    view_item.image_ref.reload()
                                    view_item.image_ref.alpha_mode = 'STRAIGHT' # FIX: Transparency
                                    # Force UI update logic if needed
                                    
                                self.report({'INFO'}, f"View '{self._view_name}' Enhanced!")
                            except Exception as e:
                                self.report({'ERROR'}, f"Failed to save image: {e}")
                        else:
                             self.report({'WARNING'}, "View image path lost.")
                    else:
                        self.report({'ERROR'}, "Failed to download image.")
                
                context.window_manager.event_timer_remove(self._timer)
                return {'FINISHED'}
            
            # TODO: Handle failures/timeout?
            
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        prefs = get_prefs(context)
        if not prefs:
            self.report({'ERROR'}, "Preferences not found")
            return {'CANCELLED'}
        
        # Get Active View
        active_view = None
        for v in context.scene.texturalia_views:
            if v.is_active_camera:
                active_view = v
                break
        
        if not active_view:
            self.report({'ERROR'}, "No active Texturalia View selected")
            return {'CANCELLED'}
            
        if not active_view.image_path or not os.path.exists(active_view.image_path):
             self.report({'ERROR'}, "View has no captured image to enhance")
             return {'CANCELLED'}
             
        self._view_name = active_view.name
        url = prefs.comfy_url or "http://127.0.0.1:8188"
        self._client = ComfyClient(url)
        
        if not self._client.is_connected():
            self.report({'ERROR'}, "ComfyUI not connected")
            return {'CANCELLED'}
            
        # 1. Upload Images (Color, Depth, Normal)
        self.report({'INFO'}, f"Uploading {active_view.name} (Color)...")
        resp = self._client.upload_image(active_view.image_path, overwrite=True)
        uploaded_color = resp.get('name') if resp else None
        
        uploaded_depth = None
        depth_path = active_view.image_path.replace(".png", "_depth.png")
        if os.path.exists(depth_path):
             self.report({'INFO'}, f"Uploading {active_view.name} (Depth)...")
             resp_d = self._client.upload_image(depth_path, overwrite=True)
             if resp_d:
                 uploaded_depth = resp_d.get('name')

        uploaded_normal = None
        norm_path = active_view.image_path.replace(".png", "_normal.png")
        if os.path.exists(norm_path):
             self.report({'INFO'}, f"Uploading {active_view.name} (Normal)...")
             resp_n = self._client.upload_image(norm_path, overwrite=True)
             if resp_n:
                 uploaded_normal = resp_n.get('name')
                 
        if not uploaded_color:
             self.report({'ERROR'}, "Base image upload failed")
             return {'CANCELLED'}
        # 2. Load Workflow (Priority: Cached -> File)
        wf_settings = context.scene.texturalia_workflow
        workflow = None
        
        if wf_settings.cached_json:
             try:
                 workflow = json.loads(wf_settings.cached_json)
             except:
                 pass
                 
        if not workflow:
            # Fallback to internal resource
            resource_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "enhance_workflow.json")
            if os.path.exists(resource_path):
                with open(resource_path, 'r') as f:
                    workflow = json.load(f)
            else:
                 self.report({'ERROR'}, "No workflow loaded")
                 return {'CANCELLED'}

        # 3. Parameters & Uploads
        uploaded_cache = {} 
        
        def get_uploaded_name(source_type, custom_path=None):
            # Helper to handle upload logic based on Source Type
            path = None
            try:
                if source_type == 'CUSTOM_FILE':
                    path = custom_path 
                    if path: path = resolve_path(path)
                elif source_type == 'VIEW_COLOR':
                    path = resolve_path(active_view.image_path)
                elif source_type == 'VIEW_DEPTH':
                    path = resolve_path(active_view.image_path).replace(".png", "_depth.png")
                elif source_type == 'VIEW_NORMAL':
                    path = resolve_path(active_view.image_path).replace(".png", "_normal.png")
                elif source_type == 'VIEW_MASK':
                    return ensure_mask_uploaded(context, active_view, self._client, uploaded_cache)

            except Exception as e:
                print(f"Texturalia Path Error: {e}")
                return None
            
            if not path or not os.path.exists(path):
                return None
                
            if path in uploaded_cache:
                return uploaded_cache[path]
            
            print(f"Texturalia: Uploading {os.path.basename(path)}...")
            resp = self._client.upload_image(path, overwrite=True)
            if resp:
                name = resp.get('name')
                uploaded_cache[path] = name
                return name
            return None

        # --- AUTO-INJECT MASK (Inpaint Mode) ---
        if active_view.generation_mode == 'INPAINT':
            print("Texturalia: Inpaint Mode - Attempting Auto-Injection...")
            mask_auto = ensure_mask_uploaded(context, active_view, self._client, uploaded_cache)
            if mask_auto:
                if inject_mask_auto(workflow, mask_auto):
                    self.report({'INFO'}, "Mask Auto-Injected")
                else:
                    print("Texturalia Warning: Inpaint active but no standard mask node found.")
            else:
                 self.report({'WARNING'}, "Inpaint: Failed to capture mask")

        # 4. Standard Node Injection (Backwards Compatibility / Default Workflow)
        # Node "11": LoadImage
        if "11" in workflow and "inputs" in workflow["11"]:
            workflow["11"]["inputs"]["image"] = uploaded_color
            
        # Node "4": Checkpoint
        ckpt_name = prefs.comfy_checkpoint
        if not ckpt_name or ckpt_name == "NONE":
             available = self._client.get_checkpoint_list()
             if available:
                 ckpt_name = available[0]
                 self.report({'INFO'}, f"Auto-selected checkpoint: {ckpt_name}")
        
        if ckpt_name and "4" in workflow:
             workflow["4"]["inputs"]["ckpt_name"] = ckpt_name
             
        # Node "3": KSampler (Seed & Denoise)
        if "3" in workflow:
             workflow["3"]["inputs"]["seed"] = random.randint(1, 1000000000000)
             if active_view:
                 workflow["3"]["inputs"]["denoise"] = active_view.enhance_denoise
                 
        # Prompts (6, 7)
        if active_view:
            if "6" in workflow: workflow["6"]["inputs"]["text"] = active_view.enhance_prompt
            if "7" in workflow: workflow["7"]["inputs"]["text"] = active_view.enhance_negative

        # 5. Dynamic Parameters (Override Standard if Mapped)
        for param in wf_settings.node_params:
            if param.node_id not in workflow:
                continue
                
            inputs = workflow[param.node_id].get("inputs", {})
            
            if param.value_type == 'INT':
                inputs[param.param_name] = param.int_val
            elif param.value_type == 'FLOAT':
                inputs[param.param_name] = param.float_val
            elif param.value_type == 'FLOAT_FACTOR':
                inputs[param.param_name] = param.float_factor
            elif param.value_type == 'STRING':
                val = param.str_val
                if val.isdigit() or (val.startswith('-') and val[1:].isdigit()):
                     try: val = int(val)
                     except: pass
                inputs[param.param_name] = val
            elif param.value_type == 'BOOL':
                inputs[param.param_name] = param.bool_val
            elif param.value_type == 'IMAGE':
                img_name = get_uploaded_name(param.image_source, param.image_path)
                if img_name:
                    inputs[param.param_name] = img_name
            
            workflow[param.node_id]["inputs"] = inputs
            
        # 6. Set Conditioning for ControlNet
        current_conditioning = ["6", 0] # Default to Positive Prompt
        
        # Helper to add node safely
        def get_free_id(wf):
            ids = [int(k) for k in wf.keys()]
            return str(max(ids) + 1)
            
        # INJECT DEPTH
        if uploaded_depth and prefs.controlnet_depth_model:
            # Add LoadImage, ControlNetLoader, ControlNetApply
            id_load = get_free_id(workflow); workflow[id_load] = {"class_type": "LoadImage", "inputs": {"image": uploaded_depth}}
            id_loader = get_free_id(workflow); workflow[id_loader] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": prefs.controlnet_depth_model}}
            
            id_apply = get_free_id(workflow)
            workflow[id_apply] = {
                "class_type": "ControlNetApply",
                "inputs": {
                    "strength": 0.8, # Default strength
                    "conditioning": current_conditioning,
                    "control_net": [id_loader, 0],
                    "image": [id_load, 0]
                }
            }
            # Update current conditioning chain
            current_conditioning = [id_apply, 0]
            self.report({'INFO'}, f" injected ControlNet Depth ({prefs.controlnet_depth_model})")

        # INJECT NORMAL
        if uploaded_normal and prefs.controlnet_normal_model:
            id_load = get_free_id(workflow); workflow[id_load] = {"class_type": "LoadImage", "inputs": {"image": uploaded_normal}}
            id_loader = get_free_id(workflow); workflow[id_loader] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": prefs.controlnet_normal_model}}
            
            id_apply = get_free_id(workflow)
            workflow[id_apply] = {
                "class_type": "ControlNetApply",
                "inputs": {
                    "strength": 0.8,
                    "conditioning": current_conditioning,
                    "control_net": [id_loader, 0],
                    "image": [id_load, 0] # Use Normal Map image
                }
            }
            current_conditioning = [id_apply, 0]
            self.report({'INFO'}, f" injected ControlNet Normal ({prefs.controlnet_normal_model})")

        # Link Final Conditioning to KSampler
        if sampler_node_id in workflow:
            # KSampler positive input is index 1 or named 'positive'? 
            # In our json (KSampler), positive is input "positive".
            workflow[sampler_node_id]["inputs"]["positive"] = current_conditioning

            
        # 4. Queue Prompt
        self.report({'INFO'}, "Queueing Enhancement...")
        print("DEBUG: Sending Workflow Payload:")
        print(json.dumps(workflow, indent=2))
        
        res = self._client.queue_prompt(workflow)
        print(f"DEBUG: Queue Response: {res}")
        
        if not res or 'prompt_id' not in res:
             self.report({'ERROR'}, "Failed to queue prompt")
             return {'CANCELLED'}
             
        self._prompt_id = res['prompt_id']
        
        self._timer = context.window_manager.event_timer_add(1.0, window=context.window)
        context.window_manager.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}



class TEXTURALIA_OT_batch_enhance(bpy.types.Operator):
    """Enhance all captured views sequentially"""
    bl_idname = "texturalia.batch_enhance"
    bl_label = "Batch Enhance All"
    bl_description = "Process all captured views with ComfyUI"
    
    _timer = None
    _client = None
    _queue = [] # List of view indices
    _total = 0
    _current_queue_index = 0
    _current_prompt_id = None
    _uploaded_cache = {}
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            # 1. CHECK STATUS OF CURRENT JOB
            if self._current_prompt_id:
                try:
                    history = self._client.get_history(self._current_prompt_id)
                    
                    if history and self._current_prompt_id in history:
                        # Finished!
                        self.process_result(context, history[self._current_prompt_id])
                        
                        # Mark done
                        self._current_prompt_id = None
                        self._current_queue_index += 1
                        
                        # Update Progress
                        progress = (self._current_queue_index / self._total) * 100.0
                        context.scene.texturalia_batch_progress = progress
                        context.scene.texturalia_batch_status = f"Completed {self._current_queue_index}/{self._total}"
                        
                except Exception as e:
                    print(f"Batch Error Polling: {e}")
                    # Skip this one on error?
                    self._current_prompt_id = None
                    self._current_queue_index += 1
            
            # 2. START NEXT JOB IF IDLE
            elif self._current_queue_index < self._total:
                view_index = self._queue[self._current_queue_index]
                view = context.scene.texturalia_views[view_index]
                
                context.scene.texturalia_batch_status = f"Processing: {view.name}..."
                
                try:
                    self._current_prompt_id = self.submit_view(context, view)
                    print(f"Batch: Submitted {view.name} -> {self._current_prompt_id}")
                except Exception as e:
                    print(f"Batch: Failed to submit {view.name}: {e}")
                    # Skip
                    self._current_queue_index += 1
            
            # 3. FINISHED ALL
            else:
                self.finish(context)
                return {'FINISHED'}
                
        return {'PASS_THROUGH'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        prefs = get_prefs(context)
        if not prefs:
            self.report({'ERROR'}, "Preferences not found")
            return {'CANCELLED'}
        
        # Connect
        url = prefs.comfy_url or "http://127.0.0.1:8188"
        self._client = ComfyClient(url)
        if not self._client.is_connected():
            self.report({'ERROR'}, "ComfyUI not connected")
            return {'CANCELLED'}
            
        # Build Queue
        # Check paths safely
        valid_queue = []
        for i, v in enumerate(context.scene.texturalia_views):
            try:
                if v.image_path:
                    p = resolve_path(v.image_path)
                    if os.path.exists(p):
                        valid_queue.append(i)
            except:
                pass
                
        self._queue = valid_queue
        self._total = len(self._queue)
        self._current_queue_index = 0
        self._current_prompt_id = None
        self._uploaded_cache = {}
        
        if self._total == 0:
            self.report({'WARNING'}, "No captured views to process (Check file save status?)")
            return {'CANCELLED'}
            
        # Init UI
        context.scene.texturalia_is_batching = True
        context.scene.texturalia_batch_progress = 0.0
        context.scene.texturalia_batch_status = "Starting..."
        
        # Start
        self._timer = context.window_manager.event_timer_add(1.0, window=context.window)
        context.window_manager.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
        
    def finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        context.scene.texturalia_is_batching = False
        context.scene.texturalia_batch_status = "Done"
        
        # Switch to Preview
        context.scene.texturalia_mode = 'PREVIEW'
        self.report({'INFO'}, "Batch Processing Complete!")

    def submit_view(self, context, view):
        """Prepares workflow and submits for a specific view"""
        wf_settings = context.scene.texturalia_workflow
        
        if not wf_settings.cached_json:
            raise Exception("No workflow loaded")
            
        workflow = json.loads(wf_settings.cached_json)
        
        # --- AUTO-INJECT MASK (Batch Inpaint) ---
        if view.generation_mode == 'INPAINT':
             print(f"Batch Inpaint: Auto-injecting mask for {view.name}...")
             mask_auto = ensure_mask_uploaded(context, view, self._client, self._uploaded_cache)
             if mask_auto:
                 inject_mask_auto(workflow, mask_auto)
        
        # Helper for uploads
        def get_uploaded_name(source_type, custom_path=None):
            path = None
            try:
                if source_type == 'CUSTOM_FILE':
                    if custom_path: path = resolve_path(custom_path)
                elif source_type == 'VIEW_COLOR':
                    path = resolve_path(view.image_path)
                elif source_type == 'VIEW_DEPTH':
                    path = resolve_path(view.image_path).replace(".png", "_depth.png")
                elif source_type == 'VIEW_NORMAL':
                    path = resolve_path(view.image_path).replace(".png", "_normal.png")
                elif source_type == 'VIEW_MASK':
                    # Batch Mask Support
                    mask_name = f"Mask_{view.name}"
                    mask_img = bpy.data.images.get(mask_name)
                    if mask_img:
                        if view.image_path:
                            base_dir = os.path.dirname(resolve_path(view.image_path))
                        else:
                            base_dir = bpy.app.tempdir
                            
                        path = os.path.join(base_dir, f"Texturalia_Mask_Temp_{view.name}.png")
                        
                        # Viewport Render of the Mask (Screen Space)
                        # We use the shared utility to ensure alignment and settings (Workbench + Texture)
                        
                        from ..utils.common import capture_view_to_file
                        
                        try:
                            # ---------------------------------------------------------
                            # TRANSIENT UV LOGIC: Create/Project UV for this View
                            # ---------------------------------------------------------
                            
                            # 0. Camera Setup (Use shared logic)
                            from ..utils.common import move_camera_to_view
                            move_camera_to_view(context, view)
                            
                            mesh_obj = context.view_layer.objects.active
                            target_uv_name = f"UV_{view.name}"
                            original_uv_name = None
                            created_transient = False
                            
                            if mesh_obj and mesh_obj.type == 'MESH':
                                # 1. CHECK FOR "UV_Mask_Project" (Created by Paint Mask Operator)
                                # If this exists, it contains the correct mapping for the painted mask.
                                # WE MUST USE IT and NOT re-project, otherwise the mask slides.
                                paint_uv = mesh_obj.data.uv_layers.get("UV_Mask_Project")
                                
                                if paint_uv:
                                    # PRIORITIZE PAINT UV
                                    print("Using existing Paint UV: UV_Mask_Project")
                                    if mesh_obj.data.uv_layers.active:
                                        original_uv_name = mesh_obj.data.uv_layers.active.name
                                        
                                    paint_uv.active_render = True
                                    paint_uv.active = True
                                    
                                # 2. FALLBACK: Existing View UV
                                elif target_uv_name in mesh_obj.data.uv_layers:
                                    # Exists: Just switch to it
                                    print(f"Switching to existing UV: {target_uv_name}")
                                    original_uv_name = mesh_obj.data.uv_layers.active.name
                                    mesh_obj.data.uv_layers[target_uv_name].active_render = True
                                    mesh_obj.data.uv_layers[target_uv_name].active = True
                                
                                # 3. FALLBACK: Create Transient
                                else:
                                    # Missing: Create & Project
                                    print(f"Creating Transient UV: {target_uv_name}")
                                    if mesh_obj.data.uv_layers.active:
                                        original_uv_name = mesh_obj.data.uv_layers.active.name
                                    
                                    # Create
                                    uv_layer = mesh_obj.data.uv_layers.new(name=target_uv_name)
                                    mesh_obj.data.uv_layers.active = uv_layer
                                    created_transient = True
                                    
                                    # Project
                                    bpy.ops.object.mode_set(mode='EDIT')
                                    bpy.ops.mesh.select_all(action='SELECT')
                                    
                                    # Find 3D View to Align
                                    area = None
                                    for a in context.screen.areas:
                                        if a.type == 'VIEW_3D':
                                            area = a
                                            break
                                            
                                    if area:
                                        region = None
                                        for r in area.regions:
                                            if r.type == 'WINDOW':
                                                region = r
                                                break
                                        
                                        if region:
                                            with context.temp_override(area=area, region=region):
                                                # Force Camera View
                                                context.scene.camera = bpy.data.objects.get("Texturalia_Camera")
                                                bpy.ops.view3d.view_camera() 
                                                
                                                # Project
                                                bpy.ops.uv.project_from_view(camera_bounds=True, correct_aspect=True, scale_to_bounds=True)
                                                
                                    bpy.ops.object.mode_set(mode='OBJECT')

                            # 3. CAPTURE (Viewport)
                            capture_view_to_file(
                                context, 
                                view, 
                                path, 
                                engine='BLENDER_WORKBENCH', 
                                shading_light='FLAT', 
                                shading_color='TEXTURE',
                                use_viewport=True
                            )
                            
                        except Exception as e:
                            print(f"Mask Render Error: {e}")
                            raise e
                        finally:
                            # 4. RESTORE / CLEANUP
                            if mesh_obj and mesh_obj.type == 'MESH':
                                # If we created it transiently, delete it to save space (8 limit)
                                if created_transient:
                                    print(f"Removing Transient UV: {target_uv_name}")
                                    uv = mesh_obj.data.uv_layers.get(target_uv_name)
                                    if uv:
                                        mesh_obj.data.uv_layers.remove(uv)
                                        
                                # Restore Original Active
                                if original_uv_name and original_uv_name in mesh_obj.data.uv_layers:
                                     print(f"Restoring Active UV: {original_uv_name}")
                                     mesh_obj.data.uv_layers[original_uv_name].active_render = True
                                     mesh_obj.data.uv_layers[original_uv_name].active = True
                    else:
                        # Fallback: Create White Mask (Full Generation)
                        w, h = 1024, 1024
                        # We don't easily have ref to image object if not loaded, but view.image_ref might fail if context changes
                        # Safe bet: 1024
                        temp_mask = bpy.data.images.new("Temp_White_Mask_Batch", width=w, height=h, alpha=False)
                        temp_mask.generated_color = (1.0, 1.0, 1.0, 1.0)
                        
                        base_dir = bpy.app.tempdir
                        path = os.path.join(base_dir, f"Texturalia_Mask_White_Batch_{view.name}.png")
                        
                        settings = context.scene.render.image_settings
                        orig_format = settings.file_format
                        settings.file_format = 'PNG'
                        
                        temp_mask.save_render(path)
                        settings.file_format = orig_format
                        
                        bpy.data.images.remove(temp_mask)
            except Exception as e:
                return None

            if not path or not os.path.exists(path):
                return None
                
            if path in self._uploaded_cache:
                return self._uploaded_cache[path]
            
            resp = self._client.upload_image(path, overwrite=True)
            if resp:
                name = resp.get('name')
                self._uploaded_cache[path] = name
                return name
            return None

        # Inject Parameters
        exposed_keys = [(p.node_id, p.param_name) for p in wf_settings.node_params]
        
        for param in wf_settings.node_params:
            if param.node_id not in workflow:
                continue
            
            inputs = workflow[param.node_id].get("inputs", {})
            
            if param.value_type == 'INT':
                inputs[param.param_name] = param.int_val
            elif param.value_type == 'FLOAT':
                inputs[param.param_name] = param.float_val
            elif param.value_type == 'FLOAT_FACTOR':
                inputs[param.param_name] = param.float_factor
            elif param.value_type == 'STRING':
                val = param.str_val
                if val.isdigit() or (val.startswith('-') and val[1:].isdigit()):
                     try: val = int(val)
                     except: pass
                inputs[param.param_name] = val
            elif param.value_type == 'BOOL':
                 inputs[param.param_name] = param.bool_val
            elif param.value_type == 'IMAGE':
                img_name = get_uploaded_name(param.image_source, param.image_path)
                if img_name:
                    inputs[param.param_name] = img_name
            
            workflow[param.node_id]["inputs"] = inputs

        # Randomize Seed
        for node_id, node_data in workflow.items():
            inputs = node_data.get("inputs", {})
            if "seed" in inputs and isinstance(inputs["seed"], int):
                 if (node_id, "seed") not in exposed_keys:
                     inputs["seed"] = random.randint(1, 1000000000000)

        # Queue
        res = self._client.queue_prompt(workflow)
        if not res or 'prompt_id' not in res:
             raise Exception("Failed to queue prompt")
             
        return res['prompt_id']

    def process_result(self, context, history_item):
        """Download and save result"""
        outputs = history_item.get('outputs', {})
        images = []
        for node_id, node_output in outputs.items():
            if 'images' in node_output:
                images.extend(node_output['images'])
        
        if images:
            img_data = images[0] # Take first
            view_index = self._queue[self._current_queue_index]
            view = context.scene.texturalia_views[view_index]
            
            raw_bytes = self._client.download_image(img_data['filename'], img_data['subfolder'], img_data['type'])
            
            if raw_bytes:
                try:
                    save_image_with_history(context, view, raw_bytes)
                except Exception as e:
                    print(f"Batch Save Error: {e}")
