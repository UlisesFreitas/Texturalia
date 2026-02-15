import bpy
import math
import os
from ..utils.common import perform_auto_zoom, get_prefs, capture_view_to_file

class TEXTURALIA_OT_add_view(bpy.types.Operator):
    """Add a new view"""
    bl_idname = "texturalia.add_view"
    bl_label = "Add View"
    bl_options = {'REGISTER', 'UNDO'}
    
    preset_name: bpy.props.EnumProperty(
        name="Preset",
        items=[
            ('CUSTOM', "Custom", "Custom view"),
            ('FRONT', "Front", "Front view (0°)"),
            ('RIGHT', "Right", "Right view (90°)"),
            ('BACK', "Back", "Back view (180°)"),
            ('LEFT', "Left", "Left view (270°)"),
            ('TOP', "Top", "Top-down view"),
            ('BOTTOM', "Bottom", "Bottom-up view"),
            ('DIAGONAL_FR', "3/4 Front-Right", "Diagonal view (45°)"),
            ('DIAGONAL_FL', "3/4 Front-Left", "Diagonal view (315°)"),
        ],
        default='CUSTOM'
    )
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "preset_name")
    
    def execute(self, context):
        view = context.scene.texturalia_views.add()
        
        # (angle, name, type, pitch_if_any)
        # Note: orbit_angle is Yaw. stored in degrees.
        
        presets = {
            'FRONT': (0.0, "Front", 'ORBIT'),
            'RIGHT': (90.0, "Right", 'ORBIT'),
            'BACK': (180.0, "Back", 'ORBIT'),
            'LEFT': (270.0, "Left", 'ORBIT'),
            'TOP': (0.0, "Top", 'TOP'),
            'BOTTOM': (0.0, "Bottom", 'BOTTOM'),
            'DIAGONAL_FR': (45.0, "3/4 Front-Right", 'ORBIT'),
            'DIAGONAL_FL': (315.0, "3/4 Front-Left", 'ORBIT'),
        }
        
        if self.preset_name in presets:
            angle, name, vtype = presets[self.preset_name]
            view.orbit_angle = angle
            view.name = name
            view.view_type = vtype
        else:
            view.name = f"View{len(context.scene.texturalia_views)}"
            view.view_type = 'ORBIT'
        
        # Get Target Z
        target_obj = bpy.data.objects.get("Texturalia_Target")
        target_z = target_obj.location.z if target_obj else 0.5
        
        view.orbit_distance = 2.0
        view.target_height = target_z
        view.camera_height = target_z
        
        # Adjust height for Top/Bottom logic (approximate)
        if view.view_type == 'TOP':
             view.camera_height = target_z + 3.0
        elif view.view_type == 'BOTTOM':
             view.camera_height = target_z - 3.0
        
        view.camera_type = 'ORTHO'
        view.camera_zoom = 3.0
        view.light_power = 3.0
        view.ui_expanded = True
        
        self.report({'INFO'}, f"Added view '{view.name}'")
        
        # Auto Zoom
        new_index = len(context.scene.texturalia_views) - 1
        perform_auto_zoom(context, new_index)
        
        return {'FINISHED'}


class TEXTURALIA_OT_create_default_views(bpy.types.Operator):
    """Create 6 default views (Front, Back, Left, Right, Top, Bottom)"""
    bl_idname = "texturalia.create_default_views"
    bl_label = "Create Default Views"
    bl_options = {'REGISTER', 'UNDO'}
    
    def invoke(self, context, event):
        if len(context.scene.texturalia_views) > 0:
            return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        # Clear existing views if confirming overwrite
        if len(context.scene.texturalia_views) > 0:
            context.scene.texturalia_views.clear()
        
        # Get Target Z
        target_obj = bpy.data.objects.get("Texturalia_Target")
        target_z = target_obj.location.z if target_obj else 0.5

        # Front (0°)
        view = context.scene.texturalia_views.add()
        view.name = "Front"
        view.view_type = 'ORBIT'
        view.orbit_angle = 0.0
        view.orbit_distance = 2.0
        view.target_height = target_z
        view.camera_height = target_z
        view.camera_type = 'PERSP' # FIX: Perspective for correct projection
        view.camera_zoom = 3.0
        view.light_power = 3.0
        view.ui_expanded = True
        
        # Back (180°)
        view = context.scene.texturalia_views.add()
        view.name = "Back"
        view.view_type = 'ORBIT'
        view.orbit_angle = 180.0
        view.orbit_distance = 2.0
        view.target_height = target_z
        view.camera_height = target_z
        view.camera_type = 'PERSP'
        view.camera_zoom = 3.0
        view.light_power = 3.0
        
        # Left (270°)
        view = context.scene.texturalia_views.add()
        view.name = "Left"
        view.view_type = 'ORBIT'
        view.orbit_angle = 270.0
        view.orbit_distance = 2.0
        view.target_height = target_z
        view.camera_height = target_z
        view.camera_type = 'PERSP'
        view.camera_zoom = 3.0
        view.light_power = 3.0
        
        # Right (90°)
        view = context.scene.texturalia_views.add()
        view.name = "Right"
        view.view_type = 'ORBIT'
        view.orbit_angle = 90.0
        view.orbit_distance = 2.0
        view.target_height = target_z
        view.camera_height = target_z
        view.camera_type = 'PERSP'
        view.camera_zoom = 3.0
        view.light_power = 3.0
        
        # Top
        view = context.scene.texturalia_views.add()
        view.name = "Top"
        view.view_type = 'TOP'
        view.orbit_distance = 3.0 
        view.target_height = target_z
        view.camera_height = target_z + 3.0
        view.camera_type = 'PERSP'
        view.camera_zoom = 3.0
        view.light_power = 3.0
        
        # Bottom
        view = context.scene.texturalia_views.add()
        view.name = "Bottom"
        view.view_type = 'BOTTOM'
        view.orbit_distance = 3.0
        view.target_height = target_z
        view.camera_height = target_z - 3.0
        view.camera_type = 'PERSP'
        view.camera_zoom = 3.0
        view.light_power = 3.0
        
        # Apply Auto Zoom to all new views
        for i in range(len(context.scene.texturalia_views)):
             perform_auto_zoom(context, i)
        
        self.report({'INFO'}, "Created 6 default views (Auto-Zoomed)")
        return {'FINISHED'}


class TEXTURALIA_OT_remove_view(bpy.types.Operator):
    """Remove this view"""
    bl_idname = "texturalia.remove_view"
    bl_label = "Remove View"
    bl_options = {'REGISTER', 'UNDO'}
    
    view_index: bpy.props.IntProperty()
    
    def execute(self, context):
        if 0 <= self.view_index < len(context.scene.texturalia_views):
            context.scene.texturalia_views.remove(self.view_index)
            self.report({'INFO'}, "View removed")
        return {'FINISHED'}


class TEXTURALIA_OT_capture_view(bpy.types.Operator):
    """Capture render from this view's camera angle"""
    bl_idname = "texturalia.capture_view"
    bl_label = "Capture"
    bl_options = {'REGISTER'}
    
    view_index: bpy.props.IntProperty()
    
    def execute(self, context):
        if self.view_index < 0 or self.view_index >= len(context.scene.texturalia_views):
            self.report({'ERROR'}, "Invalid view index")
            return {'CANCELLED'}
        
        view = context.scene.texturalia_views[self.view_index]
        
        # Output settings
        prefs = get_prefs(context)
        if not prefs:
            self.report({'ERROR'}, "Could not find Texturalia preferences")
            return {'CANCELLED'}
        
        output_dir = prefs.texturalia_output_dir
        
        if not output_dir:
            self.report({'ERROR'}, "Please set 'Texturalia Output' folder in Addon Preferences")
            return {'CANCELLED'}
            
        # Expand relative paths
        output_dir = bpy.path.abspath(output_dir)
        
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError:
                 self.report({'ERROR'}, f"Could not create directory: {output_dir}")
                 return {'CANCELLED'}
        
        # 1. Capture Color
        output_path = os.path.join(output_dir, f"{view.name}.png")
        try:
            capture_view_to_file(
                context, 
                view, 
                output_path, 
                engine='BLENDER_WORKBENCH', 
                shading_light='FLAT', 
                shading_color='TEXTURE'
            )
        except Exception as e:
            self.report({'ERROR'}, f"Capture Error: {e}")
            return {'CANCELLED'}
        
        # 2. Capture Depth & Normal (if enabled/implied)
        
        # Helper to create materials
        def create_pass_materials():
            # Depth Material
            depth_mat = bpy.data.materials.get("Texturalia_Depth_Mat")
            if not depth_mat:
                depth_mat = bpy.data.materials.new(name="Texturalia_Depth_Mat")
                depth_mat.use_nodes = True
                tree = depth_mat.node_tree
                tree.nodes.clear()
                
                # Camera Data -> Map Range -> Emission
                cam_info = tree.nodes.new('ShaderNodeCameraData')
                map_range = tree.nodes.new('ShaderNodeMapRange')
                map_range.inputs['From Min'].default_value = 0.0
                map_range.inputs['From Max'].default_value = 10.0 # Adjust based on scale?
                map_range.inputs['To Min'].default_value = 0.0
                map_range.inputs['To Max'].default_value = 1.0
                
                emission = tree.nodes.new('ShaderNodeEmission')
                output = tree.nodes.new('ShaderNodeOutputMaterial')
                
                tree.links.new(cam_info.outputs['View Z Depth'], map_range.inputs['Value'])
                tree.links.new(map_range.outputs['Result'], emission.inputs['Color'])
                tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])
                
            # Normal Material
            norm_mat = bpy.data.materials.get("Texturalia_Normal_Mat")
            if not norm_mat:
                norm_mat = bpy.data.materials.new(name="Texturalia_Normal_Mat")
                norm_mat.use_nodes = True
                tree = norm_mat.node_tree
                tree.nodes.clear()
                
                # Geometry -> Transform -> Emission
                geo = tree.nodes.new('ShaderNodeNewGeometry')
                vec_trans = tree.nodes.new('ShaderNodeVectorTransform')
                vec_trans.vector_type = 'NORMAL'
                vec_trans.convert_from = 'WORLD'
                vec_trans.convert_to = 'CAMERA'
                
                vec_math_add = tree.nodes.new('ShaderNodeVectorMath')
                vec_math_add.operation = 'ADD'
                vec_math_add.inputs[1].default_value = (1.0, 1.0, 1.0)
                
                vec_math_mul = tree.nodes.new('ShaderNodeVectorMath')
                vec_math_mul.operation = 'MULTIPLY'
                vec_math_mul.inputs[1].default_value = (0.5, 0.5, 0.5)
                
                emission = tree.nodes.new('ShaderNodeEmission')
                output = tree.nodes.new('ShaderNodeOutputMaterial')
                
                tree.links.new(geo.outputs['True Normal'], vec_trans.inputs['Vector'])
                tree.links.new(vec_trans.outputs['Vector'], vec_math_add.inputs[0])
                tree.links.new(vec_math_add.outputs['Vector'], vec_math_mul.inputs[0])
                tree.links.new(vec_math_mul.outputs['Vector'], emission.inputs['Color'])
                tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])
            
            return depth_mat, norm_mat

        depth_mat, norm_mat = create_pass_materials()
        
        # Check Eevee engine
        available_engines = {item.identifier for item in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items}
        eevee_engine = None
        if 'BLENDER_EEVEE_NEXT' in available_engines:
            eevee_engine = 'BLENDER_EEVEE_NEXT'
        elif 'BLENDER_EEVEE' in available_engines:
            eevee_engine = 'BLENDER_EEVEE'
            
        if eevee_engine:
            # Capture Depth
            depth_path = os.path.join(output_dir, f"{view.name}_depth.png")
            try:
                capture_view_to_file(context, view, depth_path, engine=eevee_engine, material_override=depth_mat)
            except Exception as e:
                print(f"Depth Capture Warning: {e}")
                
            # Capture Normal
            norm_path = os.path.join(output_dir, f"{view.name}_normal.png")
            try:
                capture_view_to_file(context, view, norm_path, engine=eevee_engine, material_override=norm_mat)
            except Exception as e:
                print(f"Normal Capture Warning: {e}")
        
        # Load Color image
        if os.path.exists(output_path):
            img_name = f"Texturalia_{view.name}"
            if img_name in bpy.data.images:
                bpy.data.images.remove(bpy.data.images[img_name])
            
            img = bpy.data.images.load(output_path)
            img.name = img_name
            # FORCE RELOAD and NO ALPHA
            img.alpha_mode = 'NONE'
            img.reload()
            img.preview_ensure()
            
            view.image_ref = img
            view.image_path = output_path
            
            # Update Image Editors
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()
            
            self.report({'INFO'}, f"Captured {view.name} (+Depth/Normal)")
        else:
            self.report({'ERROR'}, "Render failed")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class TEXTURALIA_OT_view_image(bpy.types.Operator):
    """Open captured image in Image Editor"""
    bl_idname = "texturalia.view_image"
    bl_label = "View"
    
    view_index: bpy.props.IntProperty()
    
    def execute(self, context):
        if self.view_index < 0 or self.view_index >= len(context.scene.texturalia_views):
            return {'CANCELLED'}
        
        view = context.scene.texturalia_views[self.view_index]
        if not view.image_ref:
            self.report({'WARNING'}, "No image captured yet")
            return {'CANCELLED'}
        
        # Find Image Editor
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.spaces.active.image = view.image_ref
                break
        
        return {'FINISHED'}


class TEXTURALIA_OT_set_square_resolution(bpy.types.Operator):
    """Set render resolution to 1:1 aspect ratio (square)"""
    bl_idname = "texturalia.set_square_resolution"
    bl_label = "Set Square Resolution"
    
    def execute(self, context):
        render = context.scene.render
        
        # Use the larger dimension to make it square
        max_res = max(render.resolution_x, render.resolution_y)
        render.resolution_x = max_res
        render.resolution_y = max_res
        
        self.report({'INFO'}, f"Resolution set to {max_res}x{max_res} (1:1)")
        return {'FINISHED'}
