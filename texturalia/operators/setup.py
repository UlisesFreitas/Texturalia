import bpy
import math
import mathutils

class TEXTURALIA_OT_create_rig(bpy.types.Operator):
    """Create Camera, Light and Target for multi-view capture"""
    bl_idname = "texturalia.create_rig"
    bl_label = "Create Rig"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a mesh object first.")
            return {'CANCELLED'}
        
        # --- WORK COPY LOGIC ---
        # Keep original mesh untouched, work with duplicate
        work_copy = None
        original_obj = obj
        
        if "_Texturalia_WorkCopy" in obj.name:
            # Already a work copy
            work_copy = obj
            # Try to find original (name without suffix)
            original_name = obj.name.replace("_Texturalia_WorkCopy", "")
            if original_name in bpy.data.objects:
                original_obj = bpy.data.objects[original_name]
        else:
            # Create new work copy
            copy_name = f"{obj.name}_Texturalia_WorkCopy"
            existing_copy = bpy.data.objects.get(copy_name)
            
            if existing_copy:
                work_copy = existing_copy
            else:
                # Duplicate original
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                context.view_layer.objects.active = obj
                bpy.ops.object.duplicate()
                work_copy = context.active_object
                work_copy.name = copy_name
            
            # Hide original (preserve it)
            obj.hide_viewport = True
            obj.hide_render = True
            
            # Select work copy
            bpy.ops.object.select_all(action='DESELECT')
            work_copy.select_set(True)
            context.view_layer.objects.active = work_copy
            
            # Ensure unique mesh data
            if work_copy.data == obj.data:
                work_copy.data = work_copy.data.copy()
        
        # Save both names for auto-zoom and cleanup
        context.scene["texturalia_original_mesh"] = original_obj.name
        context.scene["texturalia_work_copy"] = work_copy.name
        
        # Use work copy for all rig operations
        obj = work_copy

        # --- COLLECTION ---
        col = bpy.data.collections.get("Texturalia_Rig")
        if not col:
            col = bpy.data.collections.new("Texturalia_Rig")
            context.scene.collection.children.link(col)
        
        # CLEANUP: Remove old rig objects
        for obj_name in ["Texturalia_Camera", "Texturalia_Light", "Texturalia_Target"]:
            old_obj = bpy.data.objects.get(obj_name)
            if old_obj:
                bpy.data.objects.remove(old_obj, do_unlink=True)
            
        # --- CREATE EMPTY TARGET (at model center) ---
        # Calculate bounding box center in world space
        local_bbox_center = 0.125 * sum((mathutils.Vector(b) for b in obj.bound_box), mathutils.Vector())
        world_bbox_center = obj.matrix_world @ local_bbox_center
        
        empty = bpy.data.objects.new("Texturalia_Target", None)
        empty.location = world_bbox_center
        empty.empty_display_type = 'PLAIN_AXES'
        empty.empty_display_size = 0.3
        col.objects.link(empty)

        # --- INITIALIZE DEFAULT VIEW IF EMPTY ---
        if not context.scene.texturalia_views:
            default_view = context.scene.texturalia_views.add()
            default_view.name = "Front"
            default_view.orbit_angle = 0.0
            default_view.orbit_distance = 2.0
            default_view.target_height = world_bbox_center.z  # Use calculated center Z
            default_view.camera_height = world_bbox_center.z  # Camera at same height initially
            default_view.camera_type = 'ORTHO'
            default_view.camera_zoom = 3.0
            default_view.light_power = 3.0
            default_view.ui_expanded = True
            default_view.is_active_camera = True

        # Get active view
        active_view = None
        for view in context.scene.texturalia_views:
            if view.is_active_camera:
                active_view = view
                break
        
        if not active_view:
            active_view = context.scene.texturalia_views[0]
            active_view.is_active_camera = True
        
        # --- CREATE SINGLE CAMERA ---
        # Calculate camera position relative to TARGET
        rad = math.radians(active_view.orbit_angle - 90.0)  # 0° = Front (-Y)
        
        # Camera X/Y relative to target X/Y
        cam_x = empty.location.x + (active_view.orbit_distance * math.cos(rad))
        cam_y = empty.location.y + (active_view.orbit_distance * math.sin(rad))
        cam_z = active_view.camera_height
        
        cam_data = bpy.data.cameras.new(name="Texturalia_Camera")
        cam_obj = bpy.data.objects.new(name="Texturalia_Camera", object_data=cam_data)
        col.objects.link(cam_obj)
        
        # Camera settings
        cam_obj.data.type = active_view.camera_type
        if active_view.camera_type == 'ORTHO':
            cam_obj.data.ortho_scale = 5.0 / active_view.camera_zoom
        else:
            cam_obj.data.lens = 50.0
        
        cam_obj.data.clip_start = 0.1
        cam_obj.data.clip_end = 1000
        cam_obj.location = (cam_x, cam_y, cam_z)
        
        # Track To constraint (CRITICAL!)
        track_cam = cam_obj.constraints.new(type='TRACK_TO')
        track_cam.target = empty
        track_cam.track_axis = 'TRACK_NEGATIVE_Z'
        track_cam.up_axis = 'UP_Y'
        
        # Set as scene camera
        context.scene.camera = cam_obj
        
        # --- CREATE SINGLE LIGHT ---
        light_data = bpy.data.lights.new(name="Texturalia_Light", type='SUN')
        light_obj = bpy.data.objects.new(name="Texturalia_Light", object_data=light_data)
        col.objects.link(light_obj)
        
        # Light settings
        light_obj.data.energy = active_view.light_power
        light_obj.location = (cam_x, cam_y, cam_z)
        
        # Track To constraint for light
        track_light = light_obj.constraints.new(type='TRACK_TO')
        track_light.target = empty
        track_light.track_axis = 'TRACK_NEGATIVE_Z'
        track_light.up_axis = 'UP_Y'

        num_views = len(context.scene.texturalia_views)
        self.report({'INFO'}, f"Rig created! Camera orbits around target. {num_views} view(s).")
        return {'FINISHED'}


class TEXTURALIA_OT_cleanup(bpy.types.Operator):
    """Remove rig and restore original object"""
    bl_idname = "texturalia.cleanup"
    bl_label = "Cleanup"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Restore original mesh (unhide)
        original_mesh_name = context.scene.get("texturalia_original_mesh")
        work_copy_name = context.scene.get("texturalia_work_copy")
        
        restored = False
        if original_mesh_name and original_mesh_name in bpy.data.objects:
            original_obj = bpy.data.objects[original_mesh_name]
            original_obj.hide_viewport = False
            original_obj.hide_render = False
            
            # Select and make active
            bpy.ops.object.select_all(action='DESELECT')
            original_obj.select_set(True)
            context.view_layer.objects.active = original_obj
            
            restored = True
            self.report({'INFO'}, f"Restored '{original_mesh_name}'.")
        
        # Remove work copy
        if work_copy_name and work_copy_name in bpy.data.objects:
            work_copy = bpy.data.objects[work_copy_name]
            bpy.data.objects.remove(work_copy, do_unlink=True)
        
        # Remove rig objects
        for obj_name in ["Texturalia_Camera", "Texturalia_Light", "Texturalia_Target"]:
            obj = bpy.data.objects.get(obj_name)
            if obj:
                bpy.data.objects.remove(obj, do_unlink=True)
                
        # Remove Projectors Collection & Objects
        proj_col = bpy.data.collections.get("Texturalia_Projectors")
        if proj_col:
            for obj in proj_col.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(proj_col)
        
        # Remove collection
        col = bpy.data.collections.get("Texturalia_Rig")
        if col:
            bpy.data.collections.remove(col)
        
        # Clear views
        context.scene.texturalia_views.clear()
        
        # Clear scene properties
        if "texturalia_original_mesh" in context.scene:
            del context.scene["texturalia_original_mesh"]
        if "texturalia_work_copy" in context.scene:
            del context.scene["texturalia_work_copy"]
        # Force Disable Wireframes (Fixes any stuck state)
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                         space.overlay.show_wireframes = False

            self.report({'WARNING'}, "Original object not found. Cleanup complete.")
        else:
            self.report({'INFO'}, "Cleanup complete")
        
        return {'FINISHED'}
