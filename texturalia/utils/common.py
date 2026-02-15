import bpy
import math
import os
from mathutils import Vector

def calculate_auto_zoom(mesh_obj, camera_obj, padding_factor=1.1):
    """
    Calculate optimal orthographic scale to fit mesh in camera view.
    """
    # Get world-space bounding box corners
    bbox_corners = [mesh_obj.matrix_world @ Vector(corner) for corner in mesh_obj.bound_box]
    
    # Transform to camera space
    cam_matrix_inv = camera_obj.matrix_world.inverted()
    cam_space_corners = [cam_matrix_inv @ corner for corner in bbox_corners]
    
    # Get min/max in camera X (horizontal) and Y (vertical)
    x_coords = [c.x for c in cam_space_corners]
    y_coords = [c.y for c in cam_space_corners]
    
    width = max(x_coords) - min(x_coords)
    height = max(y_coords) - min(y_coords)
    
    # Account for render aspect ratio
    render = bpy.context.scene.render
    aspect = render.resolution_x / render.resolution_y
    
    # Ortho_scale is the visible height
    if aspect > 1.0:  # Landscape
        optimal_scale = max(height, width / aspect)
    else:  # Portrait or square
        optimal_scale = max(height * aspect, width)
    
    # Add safety padding and clamp to reasonable range
    final_scale = optimal_scale * padding_factor
    return max(0.1, min(final_scale, 20.0))  # Clamp between 0.1 and 20.0


def perform_auto_zoom(context, view_index, padding_factor=1.1):
    """Reusable auto-zoom logic for any view index"""
    scene = context.scene
    
    if view_index < 0 or view_index >= len(scene.texturalia_views):
        return False, "Invalid view index"
    
    view = scene.texturalia_views[view_index]
    
    # Find original mesh
    original_mesh_name = scene.get("texturalia_original_mesh")
    # Fallback to work copy if original not found
    if not original_mesh_name or original_mesh_name not in bpy.data.objects:
         work_copy_name = scene.get("texturalia_work_copy")
         if work_copy_name and work_copy_name in bpy.data.objects:
             original_mesh_name = work_copy_name
         else:
             return False, "Mesh not found"
    
    mesh_obj = bpy.data.objects[original_mesh_name]
    camera_obj = bpy.data.objects.get("Texturalia_Camera")
    target_obj = bpy.data.objects.get("Texturalia_Target")
    
    if not camera_obj:
        return False, "Camera not found"
    
    # Temporarily position camera to this view's angle
    saved_loc = camera_obj.location.copy()
    
    # Get target Z
    target_z = target_obj.location.z if target_obj else view.target_height
    target_x = target_obj.location.x if target_obj else 0.0
    target_y = target_obj.location.y if target_obj else 0.0
    
    if view.view_type == 'TOP':
        camera_obj.location.x = target_x
        camera_obj.location.y = target_y
        camera_obj.location.z = target_z + view.orbit_distance
    elif view.view_type == 'BOTTOM':
        camera_obj.location.x = target_x
        camera_obj.location.y = target_y
        camera_obj.location.z = target_z - view.orbit_distance
    else:  # ORBIT
        rad = math.radians(view.orbit_angle - 90.0)
        camera_obj.location.x = target_x + (view.orbit_distance * math.cos(rad))
        camera_obj.location.y = target_y + (view.orbit_distance * math.sin(rad))
        camera_obj.location.z = view.camera_height
    
    # Calculate optimal zoom
    optimal_ortho_scale = calculate_auto_zoom(mesh_obj, camera_obj, padding_factor)
    
    # Apply Zoom
    if optimal_ortho_scale > 0:
        view.camera_zoom = 5.0 / optimal_ortho_scale
        return True, f"Zoom set to {view.camera_zoom:.2f}"
    else:
        view.camera_zoom = 1.0
        return True, "Zoom fallback to 1.0"


def move_camera_to_view(context, view):
    """
    Moves the Texturalia_Camera to the specified view's position.
    """
    cam_obj = bpy.data.objects.get("Texturalia_Camera")
    empty = bpy.data.objects.get("Texturalia_Target")
    
    if not cam_obj or not empty:
         return False
         
    # 1. Setup Camera Position
    empty.location.z = view.target_height
    
    if view.view_type == 'TOP':
        cam_obj.location.x = empty.location.x
        cam_obj.location.y = empty.location.y
        cam_obj.location.z = empty.location.z + view.orbit_distance
    elif view.view_type == 'BOTTOM':
        cam_obj.location.x = empty.location.x
        cam_obj.location.y = empty.location.y
        cam_obj.location.z = empty.location.z - view.orbit_distance
    else:  # ORBIT
        rad = math.radians(view.orbit_angle - 90.0)
        cam_obj.location.x = empty.location.x + (view.orbit_distance * math.cos(rad))
        cam_obj.location.y = empty.location.y + (view.orbit_distance * math.sin(rad))
        cam_obj.location.z = view.camera_height
    
    # 2. Camera Lens/Type
    cam_obj.data.type = view.camera_type
    
    # Standard Sensor size matching Blender defaults/Texturalia setup
    cam_obj.data.sensor_fit = 'HORIZONTAL' 
    cam_obj.data.sensor_width = 36.0
    cam_obj.data.sensor_height = 36.0
    
    if view.camera_type == 'ORTHO':
        cam_obj.data.ortho_scale = 5.0 / (view.camera_zoom if view.camera_zoom > 0 else 1.0)
    else:
        cam_obj.data.lens = 50.0 
        
    context.view_layer.update()
    return True

def get_prefs(context):
    """Safely get addon preferences, handling different package names in Blender Extension"""
    # 1. Try explicit 'texturalia'
    if 'texturalia' in context.preferences.addons:
        return context.preferences.addons['texturalia'].preferences
        
    # 2. Search for any addon key ending in 'texturalia' or equal to 'texturalia'
    # This covers 'user_default.texturalia' (Extensions) and renamed folders
    for name in context.preferences.addons.keys():
        if name == "texturalia" or name.endswith(".texturalia"):
             return context.preferences.addons[name].preferences

    return None

def capture_view_to_file(context, view, filepath, engine='BLENDER_WORKBENCH', shading_light='FLAT', shading_color='TEXTURE', resolution=1024, transparent=True, override_context=None, material_override=None, use_viewport=False):
    """
    Reusable function to capture a specific view to a file.
    Can be used for Color (Workbench) or Mask (Workbench with Solid/Texture mode).
    This handles moving the camera, setting up render engine, and restoring state.
    """
    
    # Get Camera & Rig
    cam_obj = bpy.data.objects.get("Texturalia_Camera")
    light_obj = bpy.data.objects.get("Texturalia_Light")
    empty = bpy.data.objects.get("Texturalia_Target")
    
    if not cam_obj or not empty:
        raise Exception("Texturalia Rig not found")

    # SAVE STATE
    saved_cam_loc = cam_obj.location.copy()
    saved_cam_type = cam_obj.data.type
    saved_ortho_scale = cam_obj.data.ortho_scale if saved_cam_type == 'ORTHO' else None
    
    if light_obj: # Might raise error if not found? No, get returns None ok.
        saved_light_loc = light_obj.location.copy()
        
    saved_target_z = empty.location.z
    
    # Render Settings Save
    original_engine = context.scene.render.engine
    original_res_x = context.scene.render.resolution_x
    original_res_y = context.scene.render.resolution_y
    original_film_transparent = context.scene.render.film_transparent
    original_filepath = context.scene.render.filepath
    original_override = context.scene.view_layers[0].material_override
    
    # Saved Viewpoint State (if using viewport)
    saved_area_type = None
    saved_region_3d_persp = None
    
    # Ensure dir exists
    folder = os.path.dirname(filepath)
    if folder and not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except: pass

    try:
        # 1. Setup Camera Position
        empty.location.z = view.target_height
        
        if view.view_type == 'TOP':
            cam_obj.location.x = empty.location.x
            cam_obj.location.y = empty.location.y
            cam_obj.location.z = empty.location.z + view.orbit_distance
        elif view.view_type == 'BOTTOM':
            cam_obj.location.x = empty.location.x
            cam_obj.location.y = empty.location.y
            cam_obj.location.z = empty.location.z - view.orbit_distance
        else:  # ORBIT
            rad = math.radians(view.orbit_angle - 90.0)
            cam_obj.location.x = empty.location.x + (view.orbit_distance * math.cos(rad))
            cam_obj.location.y = empty.location.y + (view.orbit_distance * math.sin(rad))
            cam_obj.location.z = view.camera_height
        
        # 2. Camera Lens/Type
        cam_obj.data.type = view.camera_type
        cam_obj.data.sensor_fit = 'HORIZONTAL'
        cam_obj.data.sensor_width = 36.0
        cam_obj.data.sensor_height = 36.0
        
        if view.camera_type == 'ORTHO':
            cam_obj.data.ortho_scale = 5.0 / (view.camera_zoom if view.camera_zoom > 0 else 1.0)
        else:
            cam_obj.data.lens = 50.0 # Standard lens or custom?
            
        # 3. Light Position
        if light_obj:
            light_obj.location = cam_obj.location
            light_obj.data.energy = view.light_power
            
        # 4. Render Setup
        context.scene.render.engine = engine
        context.scene.render.resolution_x = resolution
        context.scene.render.resolution_y = resolution
        context.scene.render.film_transparent = transparent
        context.scene.render.filepath = filepath
        context.scene.render.use_file_extension = False # <--- KEY FIX
        
        if material_override:
            context.scene.view_layers[0].material_override = material_override
            
        # 5. Render Execution
        if use_viewport:
            # OpenGL Viewport Render (Captures Overlays/Paint)
            
            # Find 3D View
            area = None
            for a in context.screen.areas:
                if a.type == 'VIEW_3D':
                    area = a
                    break
            
            if not area:
                raise Exception("No 3D View found for Viewport Render")
                
            space = area.spaces.active
            
            # Force Camera View
            if space.region_3d.view_perspective != 'CAMERA':
                saved_region_3d_persp = space.region_3d.view_perspective
                space.region_3d.view_perspective = 'CAMERA'
            
            # Ensure we are looking through the correct camera
            if context.scene.camera != cam_obj:
                 context.scene.camera = cam_obj
            
            # Configure Shading for Viewport
            prev_shading_type = space.shading.type
            prev_color_type = space.shading.color_type
            prev_light = space.shading.light
            prev_overlays = space.overlay.show_overlays
            
            space.shading.type = 'SOLID'
            space.shading.color_type = shading_color # 'TEXTURE'
            space.shading.light = shading_light # 'FLAT'
            
            # For Mask, we usually want NO overlays (grid etc), but YES we want to see the paint?
            # Paint is surface, not overlay.
            # So hide overlays.
            space.overlay.show_overlays = False
            
            try:
                # Override Context for OPS
                override = context.copy()
                override['area'] = area
                for region in area.regions:
                    if region.type == 'WINDOW':
                        override['region'] = region
                        break
                        
                if hasattr(context, "temp_override"):
                    with context.temp_override(**override):
                        bpy.ops.render.opengl(write_still=True, view_context=True)
                else:
                    bpy.ops.render.opengl(override, write_still=True, view_context=True)
            finally:
                # Restore Viewport Shading
                space.shading.type = prev_shading_type
                space.shading.color_type = prev_color_type
                space.shading.light = prev_light
                space.overlay.show_overlays = prev_overlays
                
                if saved_region_3d_persp:
                     space.region_3d.view_perspective = saved_region_3d_persp
        else:
            # Standard F12 Render (Workbench/Eevee)
            if engine == 'BLENDER_WORKBENCH':
                context.scene.display.shading.light = shading_light
                context.scene.display.shading.color_type = shading_color
                context.scene.display.render_aa = 'OFF'
            
            print(f"Texturalia: Rendering to {filepath}")
            bpy.ops.render.render(write_still=True)
        
    finally:
        # RESTORE
        context.scene.render.engine = original_engine
        context.scene.render.resolution_x = original_res_x
        context.scene.render.resolution_y = original_res_y
        context.scene.render.film_transparent = original_film_transparent
        context.scene.render.filepath = original_filepath
        context.scene.render.use_file_extension = True
        context.scene.view_layers[0].material_override = original_override
        
        cam_obj.location = saved_cam_loc
        cam_obj.data.type = saved_cam_type
        if saved_cam_type == 'ORTHO' and saved_ortho_scale:
            cam_obj.data.ortho_scale = saved_ortho_scale
            
        if light_obj and saved_light_loc:
            light_obj.location = saved_light_loc
            
        empty.location.z = saved_target_z
