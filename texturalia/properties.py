import bpy
import math

# =============================
# UPDATE CALLBACKS
# =============================

def update_camera_transform(self, context):
    """Update camera position based on orbit parameters (Relative to TARGET)"""
    if not self.is_active_camera:
        return
        
    cam_obj = bpy.data.objects.get("Texturalia_Camera")
    light_obj = bpy.data.objects.get("Texturalia_Light")
    empty = bpy.data.objects.get("Texturalia_Target")
    
    if not cam_obj or not empty:
        return
        
    # Update Target Z (Height)
    empty.location.z = self.target_height
    
    if self.view_type == 'TOP':
        cam_obj.location.x = empty.location.x
        cam_obj.location.y = empty.location.y
        cam_obj.location.z = empty.location.z + self.orbit_distance
        
    elif self.view_type == 'BOTTOM':
        cam_obj.location.x = empty.location.x
        cam_obj.location.y = empty.location.y
        cam_obj.location.z = empty.location.z - self.orbit_distance
        
    else:  # ORBIT
        rad = math.radians(self.orbit_angle - 90.0)
        
        new_x = empty.location.x + (self.orbit_distance * math.cos(rad))
        new_y = empty.location.y + (self.orbit_distance * math.sin(rad))
        
        cam_obj.location.x = new_x
        cam_obj.location.y = new_y
        cam_obj.location.z = self.camera_height

    # Update Light to follow camera
    if light_obj:
        light_obj.location = cam_obj.location
        light_obj.data.energy = self.light_power


def update_target_height(self, context):
    """Move the Empty target vertically"""
    empty = bpy.data.objects.get("Texturalia_Target")
    if empty:
        empty.location.z = self.target_height


def update_camera_type(self, context):
    """Switch between ORTHO and PERSP"""
    cam_obj = bpy.data.objects.get("Texturalia_Camera")
    if cam_obj:
        cam_obj.data.type = self.camera_type


def update_camera_zoom(self, context):
    """Update ortho scale"""
    cam_obj = bpy.data.objects.get("Texturalia_Camera")
    if cam_obj and cam_obj.data.type == 'ORTHO':
        cam_obj.data.ortho_scale = 5.0 / self.camera_zoom


def update_light_power(self, context):
    """Update light energy"""
    light_obj = bpy.data.objects.get("Texturalia_Light")
    if light_obj:
        light_obj.data.energy = self.light_power


def update_active_camera(self, context):
    """When a view becomes active, move camera to its orbit position"""
    if self.is_active_camera:
        # Uncheck all other views
        for view in context.scene.texturalia_views:
            if view != self:
                view.is_active_camera = False
        
        # Move camera to this view's orbit position
        update_camera_transform(self, context)
        update_camera_type(self, context)
        update_camera_zoom(self, context)


# =============================
# PROPERTY GROUP
# =============================

class TexturaliaView(bpy.types.PropertyGroup):
    """Properties for each camera view"""
    name: bpy.props.StringProperty(name="View Name", default="View")
    
    # SIMPLE ORBIT CONTROLS
    orbit_angle: bpy.props.FloatProperty(
        name="Angle",
        description="Orbit angle in degrees (0-360)",
        min=0.0,
        max=360.0,
        default=0.0,
        step=500,
        update=update_camera_transform
    )
    
    orbit_distance: bpy.props.FloatProperty(
        name="Distance",
        description="Distance from target",
        min=0.1,
        max=50.0,
        default=2.0,
        update=update_camera_transform
    )
    
    target_height: bpy.props.FloatProperty(
        name="Target Height",
        description="Height of camera focus point (e.g., model's waist)",
        min=0.0,
        max=10.0,
        default=0.5,
        update=update_camera_transform
    )
    
    camera_height: bpy.props.FloatProperty(
        name="Camera Height",
        description="Height of camera above ground",
        min=0.0,
        max=10.0,
        default=0.5,
        update=update_camera_transform
    )
    
    # Camera settings
    camera_type: bpy.props.EnumProperty(
        name="Type",
        items=[('ORTHO', 'Orthographic', ''), ('PERSP', 'Perspective', '')],
        default='ORTHO',
        update=update_camera_type
    )
    
    camera_zoom: bpy.props.FloatProperty(
        name="Zoom",
        min=0.1,
        max=10.0,
        default=3.0,
        update=update_camera_zoom
    )
    
    light_power: bpy.props.FloatProperty(
        name="Light",
        min=0.0,
        max=10.0,
        default=3.0,
        update=update_light_power
    )
    
    # View Type (determines camera positioning logic)
    view_type: bpy.props.EnumProperty(
        name="View Type",
        items=[
            ('ORBIT', 'Orbit', 'Horizontal orbit around target (Front/Back/Left/Right)'),
            ('TOP', 'Top', 'Top-down view from above'),
            ('BOTTOM', 'Bottom', 'Bottom-up view from below'),
        ],
        default='ORBIT',
        description="Camera positioning mode"
    )
    
    # UI & Data
    ui_expanded: bpy.props.BoolProperty(default=False)
    is_active_camera: bpy.props.BoolProperty(
        name="Active",
        default=False,
        update=update_active_camera
    )
    
    # AI Enhance Settings
    enhance_prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Text description for AI enhancement",
        default="detailed, realistic, high resolution, 4k, texture"
    )
    
    enhance_negative: bpy.props.StringProperty(
        name="Negative",
        description="What to avoid",
        default="blurry, low quality, watermark, text, bad geometry"
    )
    
    enhance_denoise: bpy.props.FloatProperty(
        name="Strength",
        description="Denoising strength (0.0 = no change, 1.0 = full replacement)",
        min=0.1,
        max=1.0,
        default=0.5
    )

    image_ref: bpy.props.PointerProperty(type=bpy.types.Image)
    image_path: bpy.props.StringProperty(default="")

    # INPAINTING / MASKING (Phase 2)
    generation_mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('GLOBAL', 'Global (Txt2Img)', 'Generate whole image based on prompt'),
            ('INPAINT', 'Inpaint (Mask)', 'Regenerate only masked areas'),
        ],
        default='GLOBAL'
    )
    
    mask_image_path: bpy.props.StringProperty(default="", subtype='FILE_PATH')


def update_texturalia_mode(self, context):
    """Switch between EDIT (Clean) and PREVIEW (Projected) modes"""
    mode = context.scene.texturalia_mode
    work_copy_name = context.scene.get("texturalia_work_copy")
    
    if not work_copy_name or work_copy_name not in bpy.data.objects:
        return
        
    obj = bpy.data.objects[work_copy_name]
    
    if mode == 'EDIT':
        # 1. Switch Material to Baked (Priority) or Base
        # We try to find the best "Clean" material
        target_mat = bpy.data.materials.get("Texturalia_Baked_Mat")
        
        # Decide which UV to activate based on material
        target_uv = None
        
        if target_mat:
             if obj.data.materials:
                obj.data.materials[0] = target_mat
             else:
                obj.data.materials.append(target_mat)
             
             # If using Baked Mat, use UV_Bake
             target_uv = "UV_Bake"
        else:
            # Fallback to Original Material
            # Try finding the stored original material
            original_mat_name = context.scene.get("texturalia_original_material")
            original_mat = None
            
            if original_mat_name:
                original_mat = bpy.data.materials.get(original_mat_name)
            
            if original_mat:
                 if obj.data.materials:
                    obj.data.materials[0] = original_mat
                 else:
                    obj.data.materials.append(original_mat)
            else:
                 # Last resort: Any non-live material
                 for m in bpy.data.materials:
                    if m.name != "Texturalia_Live_Mat":
                        # Assign and break
                        if obj.data.materials:
                            obj.data.materials[0] = m
                        else:
                            obj.data.materials.append(m)
                        break
            
            # If we can't find Baked, use Original UV
            target_uv = context.scene.get("texturalia_original_uv")
        
        # Activate UV
        if target_uv and target_uv in obj.data.uv_layers:
            obj.data.uv_layers[target_uv].active = True
            obj.data.uv_layers[target_uv].active_render = True
        
        # 2. Disable UV Project Modifiers (Visual cleanup)
        for mod in obj.modifiers:
            if mod.type == 'UV_PROJECT':
                mod.show_viewport = False
                mod.show_render = False
                
    elif mode == 'PREVIEW':
        # 1. Switch Material to Live
        target_mat = bpy.data.materials.get("Texturalia_Live_Mat")
        
        if target_mat:
            if obj.data.materials:
                obj.data.materials[0] = target_mat
            else:
                obj.data.materials.append(target_mat)
        
        # 2. Enable UV Project Modifiers
        for mod in obj.modifiers:
            if mod.type == 'UV_PROJECT':
                mod.show_viewport = True
                mod.show_render = True

# =============================
# WORKFLOW PROPERTIES
# =============================

class TexturaliaNodeParam(bpy.types.PropertyGroup):
    """Dynamic parameter for ComfyUI nodes"""
    node_id: bpy.props.StringProperty()
    node_title: bpy.props.StringProperty()
    param_name: bpy.props.StringProperty()
    
    # Type: 'INT', 'FLOAT', 'STRING', 'BOOL', 'IMAGE'
    value_type: bpy.props.StringProperty() 
    
    # Values
    int_val: bpy.props.IntProperty()
    float_val: bpy.props.FloatProperty(step=1, precision=3)
    float_factor: bpy.props.FloatProperty(name="Factor", default=1.0, min=0.0, max=1.0, subtype='FACTOR', step=1, precision=3)
    str_val: bpy.props.StringProperty()
    bool_val: bpy.props.BoolProperty()
    
    # Image Input Strategy
    # Options: [CUSTOM_FILE, VIEW_COLOR, VIEW_DEPTH, VIEW_NORMAL]
    image_source: bpy.props.EnumProperty(
        name="Source",
        items=[
            ('CUSTOM_FILE', 'Custom File', 'Upload a specific file from disk'),
            ('VIEW_COLOR', 'View Color', 'Use the captured Color image of the active view'),
            ('VIEW_DEPTH', 'View Depth', 'Use the captured Depth map of the active view'),
            ('VIEW_NORMAL', 'View Normal', 'Use the captured Normal map of the active view'),
            ('VIEW_MASK', 'View Mask', 'Use the painted mask of the active view'),
        ],
        default='VIEW_COLOR'
    )
    
    image_path: bpy.props.StringProperty(
        subtype='FILE_PATH',
        description="Select image file to upload"
    )
    
    # UI Grouping
    node_group: bpy.props.StringProperty()

def get_workflow_items(self, context):
    """Scan resources/workflows and user folder for .json files"""
    items = []
    
    # 1. Built-in
    # 1. Built-in
    try:
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        res_dir = os.path.join(addon_dir, "resources", "workflows")
        
        if os.path.exists(res_dir):
            files = os.listdir(res_dir)
            for f in files:
                if f.endswith(".json") and not f.endswith(".map.json"):
                    items.append((f, f, "Built-in Workflow"))
        else:
            print(f"Texturalia Warning: Workflow dir not found at {res_dir}")
            
    except Exception as e:
        print(f"Texturalia Error scanning workflows: {e}")
    
    # 2. User Folder (TODO: Add to Preferences)
    # prefs = context.preferences.addons[__package__].preferences
    # ...
    
    if not items:
        return [("NONE", "No Workflows Found", "")]
        
    return items

class TexturaliaWorkflowSettings(bpy.types.PropertyGroup):
    """Stores workflow state"""
    
    # Selection from list
    workflow_name: bpy.props.EnumProperty(
        name="Workflow",
        description="Select a workflow to use",
        items=get_workflow_items
    )
    
    # Specific file path is derived from name, or custom load?
    # Retexturity uses a File Path prop. 
    # Let's support both? Or just the Enum.
    # Enum is safer for "bundled" ones.
    
    workflow_file: bpy.props.StringProperty(
        name="Workflow JSON",
        subtype='FILE_PATH',
        description="Path to API-format .json workflow"
    )
    
    # Collection of Exposed Parameters
    node_params: bpy.props.CollectionProperty(type=TexturaliaNodeParam)
    
    # Internal storage for loaded JSON
    cached_json: bpy.props.StringProperty()
    
    # Smart Mapping
    input_node_id: bpy.props.StringProperty(name="Input Node ID")
    output_node_id: bpy.props.StringProperty(name="Output Node ID")

