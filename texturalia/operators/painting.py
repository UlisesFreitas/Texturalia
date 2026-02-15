import bpy
import os

class TEXTURALIA_OT_setup_mask(bpy.types.Operator):
    """Create mask image and enter Texture Paint mode"""
    bl_idname = "texturalia.setup_mask"
    bl_label = "Paint Mask"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        from ..utils.common import move_camera_to_view
        
        # 1. Get Active View
        active_view = None
        for v in context.scene.texturalia_views:
            if v.is_active_camera:
                active_view = v
                break
        
        if not active_view:
            self.report({'ERROR'}, "No active view selected")
            return {'CANCELLED'}
        
        # 1b. Move Camera to View Position (Critical for Projection)
        if not move_camera_to_view(context, active_view):
            self.report({'ERROR'}, "Failed to position camera (Rig missing?)")
            return {'CANCELLED'}
            
        # 2. Check/Create Mask Image
        mask_name = f"Mask_{active_view.name}"
        mask_img = bpy.data.images.get(mask_name)
        
        if not mask_img:
            # Create new 1024x1024 Black image
            mask_img = bpy.data.images.new(name=mask_name, width=1024, height=1024, alpha=True)
            # Init to Transparent Black (0,0,0,0) so we can see the model/background
            pixels = [0.0, 0.0, 0.0, 0.0] * (1024 * 1024)
            mask_img.pixels = pixels
            
        # Store path reference (even if internal mostly)
        active_view.mask_image_path = "" 
        
        # 3. Setup Texture Paint
        work_copy_name = context.scene.get("texturalia_work_copy")
        if work_copy_name and work_copy_name in bpy.data.objects:
            obj = bpy.data.objects[work_copy_name]
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            
            # --- UV PROJECTION LOGIC ---
            # Create/Overwrite "UV_Mask_Project" for painting
            target_uv_name = "UV_Mask_Project"
            self.report({'INFO'}, f"Setting up UV: {target_uv_name} on {obj.name}")
            
            # Remove if exists to force fresh
            if target_uv_name in obj.data.uv_layers:
                 obj.data.uv_layers.remove(obj.data.uv_layers[target_uv_name])
            
            # Create
            uv_layer = obj.data.uv_layers.new(name=target_uv_name)
            if not uv_layer:
                self.report({'ERROR'}, "Failed to create UV Layer")
                return {'CANCELLED'}
            
            self.report({'INFO'}, "Created UV Layer")
                
            # Make Active
            obj.data.uv_layers.active = uv_layer
            uv_layer.active_render = True
            
            # Project From View
            # We need to be in Edit Mode and looking through camera
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'INFO'}, "Switched to Edit Mode")
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
            
            # Return to Texture Paint
            bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
            
            # Ensure Viewport Formatting
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                             space.shading.type = 'SOLID'
                             space.shading.color_type = 'TEXTURE'
                             space.overlay.show_overlays = True 
                             space.overlay.show_wireframes = False
            
            # 4. Setup Tool/Image
            try:
                ts = context.tool_settings
                if hasattr(ts, "image_paint"):
                     ts.image_paint.canvas = mask_img
                     ts.image_paint.mode = 'IMAGE' 
                     ts.image_paint.canvas = mask_img
            except Exception as e:
                print(f"Mask Setup Warning: {e}")
                
            # Create/Get Dedicated Brush
            brush_name = "Texturalia_Mask_Brush"
            target_brush = bpy.data.brushes.get(brush_name)
            if not target_brush:
                target_brush = bpy.data.brushes.new(name=brush_name, mode='TEXTURE_PAINT')
                
            # Try to Assign to Tool
            brush = target_brush
            try:
                ts.image_paint.brush = target_brush
            except Exception as e:
                print(f"Mask Brush Warning: Could not assign custom brush ({e}). Using active.")
                if ts.image_paint.brush:
                    brush = ts.image_paint.brush

            # Configure Brush (Hardness, Color, etc.)
            if brush:
                brush.color = (1.0, 1.0, 1.0)
                brush.strength = 1.0
                brush.blend = 'MIX'
                
            # Show Image in Editor
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.spaces.active.image = mask_img
                    
        self.report({'INFO'}, "Ready to Paint Mask (White = Regenerate)")
        return {'FINISHED'}

class TEXTURALIA_OT_clear_mask(bpy.types.Operator):
    """Reset the mask to black"""
    bl_idname = "texturalia.clear_mask"
    bl_label = "Clear Mask"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_view = None
        for v in context.scene.texturalia_views:
            if v.is_active_camera:
                active_view = v
                break
                
        if active_view:
            mask_name = f"Mask_{active_view.name}"
            mask_img = bpy.data.images.get(mask_name)
            if mask_img:
                pixels = [0.0, 0.0, 0.0, 1.0] * (mask_img.size[0] * mask_img.size[1])
                mask_img.pixels = pixels
                mask_img.update()
                self.report({'INFO'}, "Mask Cleared")
        
        return {'FINISHED'}

class TEXTURALIA_OT_save_mask(bpy.types.Operator):
    """Save the current mask to the output folder"""
    bl_idname = "texturalia.save_mask"
    bl_label = "Save Mask"
    bl_description = "Capture and save the current mask to disk"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        from ..utils.common import capture_view_to_file, get_prefs
        
        # 1. Active View
        active_view = None
        for v in context.scene.texturalia_views:
            if v.is_active_camera:
                active_view = v
                break
        
        if not active_view:
            self.report({'ERROR'}, "No active view")
            return {'CANCELLED'}

        # 2. Output Path
        prefs = get_prefs(context)
        out_dir = prefs.texturalia_output_dir if prefs else ""
        if not out_dir:
            out_dir = bpy.app.tempdir
            
        filename = f"Mask_{active_view.name}.png"
        path = os.path.join(os.path.abspath(bpy.path.abspath(out_dir)), filename)
        
        # 3. Capture Process (Alpha Clip Logic)
        work_copy_name = context.scene.get("texturalia_work_copy")
        if not work_copy_name or work_copy_name not in bpy.data.objects:
             self.report({'ERROR'}, "Work copy object not found")
             return {'CANCELLED'}
             
        mesh_obj = bpy.data.objects[work_copy_name]
        
        # -- Prepare UV --
        # We assume UV_Mask_Project exists if user painted, but we can verify/re-project?
        # Re-projecting might destroy manual paint alignment if view moved.
        # Just activate existing if possible, or fallback.
        
        target_uv_name = "UV_Mask_Project"
        original_uv_name = mesh_obj.data.uv_layers.active.name if mesh_obj.data.uv_layers.active else None
        created_transient = False
        
        if mesh_obj.data.uv_layers.get("UV_Mask_Project"):
             uv_l = mesh_obj.data.uv_layers["UV_Mask_Project"]
             uv_l.active = True
             uv_l.active_render = True
        else:
             # Fallback: Current view UV?
             target_uv_name = f"UV_{active_view.name}"
             if target_uv_name in mesh_obj.data.uv_layers:
                 uv_l = mesh_obj.data.uv_layers[target_uv_name]
                 uv_l.active = True
                 uv_l.active_render = True
             else:
                 self.report({'WARNING'}, "No specific Mask UV found, result might vary.")
                 
        # -- Material Override --
        original_materials = [s.material for s in mesh_obj.material_slots]
        
        # Find Mask Image
        mask_name = f"Mask_{active_view.name}"
        mask_img = bpy.data.images.get(mask_name)
        if not mask_img:
            # Fallback (Dot)
            alt_name = f"Mask.{active_view.name}"
            mask_img = bpy.data.images.get(alt_name)
            
        if not mask_img:
            self.report({'ERROR'}, "No paint mask found in memory")
            return {'CANCELLED'}
            
        # Create Temp Material (Emission for pure B/W)
        temp_mat = bpy.data.materials.new(name="Texturalia_Temp_Saver")
        temp_mat.use_nodes = True
        temp_mat.blend_method = 'OPAQUE' # Ignore alpha, render RGB directly
        try:
            temp_mat.shadow_method = 'NONE'
        except AttributeError:
            pass
        
        tree = temp_mat.node_tree
        tree.nodes.clear()
        
        # Emission Node
        emis = tree.nodes.new('ShaderNodeEmission')
        emis.location = (0,0)
        emis.inputs['Strength'].default_value = 1.0
        
        # Image Node
        tex = tree.nodes.new('ShaderNodeTexImage')
        tex.location = (-300, 0)
        tex.image = mask_img
        
        # Output
        out = tree.nodes.new('ShaderNodeOutputMaterial')
        out.location = (300,0)
        
        # Link Color -> Color
        tree.links.new(tex.outputs['Color'], emis.inputs['Color'])
        tree.links.new(emis.outputs['Emission'], out.inputs['Surface'])
        
        # Apply Material
        mesh_obj.data.materials.clear()
        mesh_obj.data.materials.append(temp_mat)
        
        # -- Capture --
        rs = context.scene.render.image_settings
        orig_fmt = rs.file_format
        orig_mode = rs.color_mode
        
        try:
            rs.file_format = 'PNG'
            rs.color_mode = 'RGBA'
            
            capture_view_to_file(
                context, 
                active_view, 
                path, 
                engine='BLENDER_EEVEE', 
                use_viewport=False
            )
            
            self.report({'INFO'}, f"Mask saved to: {filename}")
            if os.path.exists(path):
                print(f"Mask Saved Full Path: {path}")
            
        except Exception as e:
            self.report({'ERROR'}, f"Save failed: {e}")
            
        finally:
            rs.file_format = orig_fmt
            rs.color_mode = orig_mode
            
            # Restore
            mesh_obj.data.materials.clear()
            for m in original_materials:
                mesh_obj.data.materials.append(m)
                
            if original_uv_name and original_uv_name in mesh_obj.data.uv_layers:
                 mesh_obj.data.uv_layers[original_uv_name].active_render = True
                 mesh_obj.data.uv_layers[original_uv_name].active = True
                 
            bpy.data.materials.remove(temp_mat)
            
        return {'FINISHED'}
