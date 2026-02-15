import bpy
import os
import math
from mathutils import Vector

class TEXTURALIA_OT_create_live_shader(bpy.types.Operator):
    """Create live non-destructive projection for preview"""
    bl_idname = "texturalia.create_live_shader"
    bl_label = "Live Preview"
    
    def execute(self, context):
        # 1. Get objects
        original_mesh_name = context.scene.get("texturalia_original_mesh")
        work_copy_name = context.scene.get("texturalia_work_copy")
        
        if not work_copy_name or work_copy_name not in bpy.data.objects:
             self.report({'ERROR'}, "Work copy not found. Create rig first.")
             return {'CANCELLED'}
        
        # Ensure Object Mode
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
            
        obj = bpy.data.objects[work_copy_name]
        
        # FIX: Apply Transforms (Scale & Rotation) to ensure UV Project works correctly
        # This fixes determining correct world space for normals and projections
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        
        # 2. Check for captured views
        views_with_images = [v for v in context.scene.texturalia_views if v.image_ref]
        
        if not views_with_images:
            self.report({'WARNING'}, "No captured images found. Capture some views first.")
            return {'CANCELLED'}
            
        # 3. Create Projectors Collection
        proj_col = bpy.data.collections.get("Texturalia_Projectors")
        if not proj_col:
            proj_col = bpy.data.collections.new("Texturalia_Projectors")
            context.scene.collection.children.link(proj_col)
            
        # 4. Setup Material
        mat_name = "Texturalia_Live_Mat"
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
        
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
            
        # 5. Clear Modifiers (Start fresh)
        for mod in obj.modifiers:
            if mod.name.startswith("Texturalia_Proj"):
                obj.modifiers.remove(mod)
        
        # 6. Create Projectors for each View
        
        # Clear existing nodes
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        
        # Base Emission Shader (Replaces Principled BSDF for Pure Color)
        emission = nodes.new('ShaderNodeEmission')
        emission.location = (0, 0)
        
        output = nodes.new('ShaderNodeOutputMaterial')
        output.location = (300, 0)
        links.new(emission.outputs['Emission'], output.inputs['Surface'])
        
        prev_shader_socket = None
        
        for i, view in enumerate(views_with_images):
            # A. Create Projector Object (CAMERA)
            proj_name = f"Texturalia_Projector_{view.name}"
            proj_obj = bpy.data.objects.get(proj_name)
            if proj_obj:
               bpy.data.objects.remove(proj_obj, do_unlink=True)
            
            # Create Camera Data
            cam_data = bpy.data.cameras.new(name=f"CamData_{view.name}")
            proj_obj = bpy.data.objects.new(proj_name, cam_data)
            proj_col.objects.link(proj_obj)
            
            # Setup Camera Parameters (Match View)
            proj_obj.data.type = view.camera_type
            # FIX: Force Sensor Fit and Size to match Capture (Square 1:1)
            # This ensures the projector aspect ratio matches the captured image exactly.
            proj_obj.data.sensor_fit = 'HORIZONTAL'
            proj_obj.data.sensor_width = 36.0
            proj_obj.data.sensor_height = 36.0
            
            if view.camera_type == 'ORTHO':
                proj_obj.data.ortho_scale = 5.0 / view.camera_zoom
            else:
                 proj_obj.data.lens = 50.0 # Standard 50mm for Persp
            
            # Position it!
            target_obj = bpy.data.objects.get("Texturalia_Target")
            if not target_obj:
                 self.report({'ERROR'}, "Target missing")
                 return {'CANCELLED'}
            
            t_loc = target_obj.location
            t_z = view.target_height
            
            if view.view_type == 'TOP':
                proj_obj.location = (t_loc.x, t_loc.y, t_z + view.orbit_distance)
            elif view.view_type == 'BOTTOM':
                proj_obj.location = (t_loc.x, t_loc.y, t_z - view.orbit_distance)
            else:
                rad = math.radians(view.orbit_angle - 90.0)
                proj_obj.location.x = t_loc.x + (view.orbit_distance * math.cos(rad))
                proj_obj.location.y = t_loc.y + (view.orbit_distance * math.sin(rad))
                proj_obj.location.z = view.camera_height
            
            # Rotation: Track To Target
            track = proj_obj.constraints.new(type='TRACK_TO')
            track.target = target_obj
            track.track_axis = 'TRACK_NEGATIVE_Z'
            track.up_axis = 'UP_Y'
            
            # Force update to apply constraint rotation
            context.view_layer.update()
            
            print(f"DEBUG: Created Projector {proj_name} at {proj_obj.location}")

            # Ensure UV Layer exists and is fresh
            uv_name = f"UV_{view.name}"
            if uv_name in obj.data.uv_layers:
                obj.data.uv_layers.remove(obj.data.uv_layers[uv_name])
                
            uv_layer = obj.data.uv_layers.new(name=uv_name)
            final_uv_name = uv_layer.name
            
            # B. Add UV Project Modifier
            mod_name = f"Texturalia_Proj_{view.name}"
            mod = obj.modifiers.new(name=mod_name, type='UV_PROJECT')
            mod.projectors[0].object = proj_obj
            mod.uv_layer = final_uv_name
            
            # Ensure modifier uses square aspect since our image/sensor is square
            mod.aspect_x = 1.0
            mod.aspect_y = 1.0
            mod.scale_x = 1.0
            mod.scale_y = 1.0
            
            # C. Add Shader Nodes with ROBUST Camera-Space Culling
            
            # Image Texture
            tex_node = nodes.new('ShaderNodeTexImage')
            tex_node.image = view.image_ref
            tex_node.extension = 'CLIP' # Don't repeat
            tex_node.location = (-800, i * 450)
            
            # UV Map Node
            uv_node = nodes.new('ShaderNodeUVMap')
            uv_node.uv_map = final_uv_name
            uv_node.location = (-1000, i * 450 + 50)
            links.new(uv_node.outputs['UV'], tex_node.inputs['Vector'])
            
            # --- 1. BACKFACE CULLING (Camera Space) ---
            # Transform Normal to Projector Space. If Z > 0, it points at the camera.
            
            # Geometry (Normal)
            geo_node = nodes.new('ShaderNodeNewGeometry')
            geo_node.location = (-1600, i * 450 - 200)
            
            # Vector Transform (World -> Object [Projector])
            vec_trans = nodes.new('ShaderNodeVectorTransform')
            vec_trans.vector_type = 'NORMAL'
            vec_trans.convert_from = 'WORLD'
            vec_trans.convert_to = 'OBJECT'
            vec_trans.location = (-1400, i * 450 - 200)
            
            # We can't explicitly set the 'Object' input of Vector Transform node via Python easily 
            # if we can't link it. But Vector Transform typically uses the active object?
            # WAIT. ShaderNodeVectorTransform doesn't have an 'Object' input socket. 
            # It uses the object executing the shader or view?
            # It only has Start/End spaces. Only "Object" means 'The Object with the material'.
            # It CANNOT transform into 'Another Object's Space'. 
            # CRITICAL FAIL of that plan.
            
            # ALTERNATIVE: Use Vector Math with Dot Product again, but CORRECTLY for Ortho.
            # OR: Use Texture Coordinate (Object=Projector).
            # The Texture Coordinate 'Object' output gives Position in Projector Space.
            # But we need Normal in Projector Space.
            
            # REVERT TO DOT PRODUCT but handle Ortho/Persp distinction?
            # Or use "Raycast" equivalent?
            
            # Let's use the 'Texture Coordinate' -> Object (Projector) -> Position logic for Frustum.
            # For Normal: We can rotate the Normal by the Projector's inverse rotation manually?
            # We can calculate the Projector's Forward Vector (View Vector) in World Space (Python)
            # and Dot it with Normal (World Space).
            # This works for Ortho perfectly (View Vector is constant).
            
            # Get Projector Forward Vector (World Space)
            # Camera looks down local -Z.
            proj_rot = proj_obj.matrix_world.to_3x3()
            view_vec = proj_rot @ Vector((0, 0, -1)) # Forward direction
            
            # Dot(Normal, ViewVec).
            # Normal points OUT. ViewVec points IN.
            # Facing: Angle ~180. Dot < 0.
            # Backfacing: Angle ~0. Dot > 0.
            # Mask: Less Than 0.
            
            norm_node = nodes.new('ShaderNodeVectorMath')
            norm_node.operation = 'DOT_PRODUCT'
            norm_node.location = (-1200, i * 450 - 200)
            norm_node.inputs[1].default_value = view_vec
            links.new(geo_node.outputs['Normal'], norm_node.inputs[0])
            
            # Check Facing
            facing_check = nodes.new('ShaderNodeMath')
            facing_check.operation = 'LESS_THAN'
            facing_check.inputs[1].default_value = -0.05
            facing_check.location = (-1000, i * 450 - 200)
            links.new(norm_node.outputs['Value'], facing_check.inputs[0])
            
            # --- 2. FRUSTUM Z-CULLING (Object Space) ---
            # Use TexCoord Object to prune stuff behind camera
            
            tex_coord = nodes.new('ShaderNodeTexCoord')
            tex_coord.object = proj_obj 
            tex_coord.location = (-1400, i * 450 - 400)
            
            sep_xyz = nodes.new('ShaderNodeSeparateXYZ')
            sep_xyz.location = (-1200, i * 450 - 400)
            links.new(tex_coord.outputs['Object'], sep_xyz.inputs['Vector'])
            
            # Camera looks down -Z. So visible stuff has Z < 0.
            # Everything with Z > 0 is behind camera.
            z_check = nodes.new('ShaderNodeMath')
            z_check.operation = 'LESS_THAN' 
            z_check.inputs[1].default_value = 0.0 
            z_check.location = (-1000, i * 450 - 400)
            links.new(sep_xyz.outputs['Z'], z_check.inputs[0])
            
            # --- 3. COMBINE ---
            combine = nodes.new('ShaderNodeMath')
            combine.operation = 'MULTIPLY'
            combine.location = (-800, i * 450 - 300)
            links.new(facing_check.outputs['Value'], combine.inputs[0])
            links.new(z_check.outputs['Value'], combine.inputs[1])
            
            # --- 4. APPLY TO ALPHA ---
            final_alpha = nodes.new('ShaderNodeMath')
            final_alpha.operation = 'MULTIPLY'
            final_alpha.location = (-600, i * 450 - 100)
            links.new(tex_node.outputs['Alpha'], final_alpha.inputs[0])
            links.new(combine.outputs['Value'], final_alpha.inputs[1])
            
            # Mix logic
            if prev_shader_socket is None:
                mix_node = nodes.new('ShaderNodeMixRGB')
                mix_node.location = (-400, i * 450)
                mix_node.blend_type = 'MIX'
                
                mix_node.inputs[1].default_value = (0.0, 0.0, 0.0, 1.0) 
                links.new(final_alpha.outputs['Value'], mix_node.inputs['Fac']) 
                links.new(tex_node.outputs['Color'], mix_node.inputs[2]) 
                
                prev_shader_socket = mix_node.outputs['Color']
            else:
                mix_node = nodes.new('ShaderNodeMixRGB')
                mix_node.location = (-400, i * 450)
                mix_node.blend_type = 'MIX'
                
                links.new(final_alpha.outputs['Value'], mix_node.inputs['Fac']) 
                links.new(prev_shader_socket, mix_node.inputs[1]) 
                links.new(tex_node.outputs['Color'], mix_node.inputs[2])
                
                prev_shader_socket = mix_node.outputs['Color']
                
        # Connect to Surface - SHADELESS (Emission)
        # Because AI textures have baked lighting, we don't want Blender lights washing them out.
        if prev_shader_socket:
             links.new(prev_shader_socket, emission.inputs['Color'])
             emission.inputs['Strength'].default_value = 1.0
            
        # FIX: Force MATERIAL Preview so user sees the shader result (Solid view is confusing with UVs)
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'
        
        self.report({'INFO'}, "Live Preview Updated")
        return {'FINISHED'}


class TEXTURALIA_OT_bake_texture(bpy.types.Operator):
    """Bake the live preview to a single texture"""
    bl_idname = "texturalia.bake_texture"
    bl_label = "Bake Texture"
    
    def execute(self, context):
        # FIX: Force reload all view images to ensure Bake uses latest ComfyUI results
        for view in context.scene.texturalia_views:
            if view.image_ref:
                view.image_ref.reload()
                view.image_ref.alpha_mode = 'STRAIGHT' # Ensure correct transparency
        
        work_copy_name = context.scene.get("texturalia_work_copy")
        if not work_copy_name or work_copy_name not in bpy.data.objects:
            self.report({'ERROR'}, "Work copy not found.")
            return {'CANCELLED'}
        
        obj = bpy.data.objects[work_copy_name]
        
        # Ensure Object Mode and Active
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 1. OPTIMIZE VIEWPORT (Fix Freeze)
        original_shading = 'SOLID'
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        original_shading = space.shading.type
                        space.shading.type = 'SOLID'

        try:
            # 2. CREATE UV MAP FOR BAKE
            bake_uv_name = "UV_Bake"
            uv_layer = obj.data.uv_layers.get(bake_uv_name)
            if not uv_layer:
                uv_layer = obj.data.uv_layers.new(name=bake_uv_name)
            
            obj.data.uv_layers.active = uv_layer
            
            # Run Smart UV Project
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(island_margin=0.01)
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # 3. CREATE DESTINATION IMAGE
            img_name = "Texturalia_Bake_Result"
            img = bpy.data.images.get(img_name)
            if not img:
                img = bpy.data.images.new(img_name, width=2048, height=2048)
            
            # 4. PREPARE MATERIAL FOR BAKE
            mat = obj.active_material
            if not mat or not mat.use_nodes:
                self.report({'ERROR'}, "Live shader not found. Run Live Preview first.")
                return {'CANCELLED'}
                
            nodes = mat.node_tree.nodes
            
            # Create Target Node
            bake_node = nodes.new('ShaderNodeTexImage')
            bake_node.name = "Bake_Target"
            bake_node.image = img
            bake_node.location = (1500, 300)
            nodes.active = bake_node
            
            # 5. CONFIGURE RENDER SETTINGS
            if context.scene.render.engine != 'CYCLES':
                context.scene.render.engine = 'CYCLES'
                
            context.scene.cycles.device = 'CPU'
            context.scene.cycles.samples = 1
            context.scene.cycles.use_adaptive_sampling = False
            
            # 6. BAKE
            self.report({'INFO'}, "Baking... (Please wait, UI may freeze)")
            
            bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, save_mode='INTERNAL')
            
            # Automatic Save
            if context.blend_data.filepath:
                folder = os.path.dirname(context.blend_data.filepath)
                save_path = os.path.join(folder, "Texturalia_Result.png")
                img.filepath_raw = save_path
                img.file_format = 'PNG'
                img.save()
                self.report({'INFO'}, f"Bake saved to: {save_path}")
            else:
                self.report({'WARNING'}, "Blend file not saved. Image in memory only.")
                
            nodes.remove(bake_node)
            
            # 7. APPLY BAKED MATERIAL TO OBJECT
            baked_mat_name = "Texturalia_Baked_Mat"
            baked_mat = bpy.data.materials.get(baked_mat_name)
            if not baked_mat:
                baked_mat = bpy.data.materials.new(name=baked_mat_name)
                baked_mat.use_nodes = True
            
            baked_mat.use_nodes = True
            bk_nodes = baked_mat.node_tree.nodes
            bk_links = baked_mat.node_tree.links
            bk_nodes.clear()
            
            bsdf = bk_nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.location = (0, 0)
            
            tex_img = bk_nodes.new('ShaderNodeTexImage')
            tex_img.image = img
            tex_img.location = (-300, 0)
            
            output = bk_nodes.new('ShaderNodeOutputMaterial')
            output.location = (300, 0)
            
            bk_links.new(tex_img.outputs['Color'], bsdf.inputs['Base Color'])
            bk_links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
            
            if obj.data.materials:
                obj.data.materials[0] = baked_mat
            else:
                obj.data.materials.append(baked_mat)
            
            # 8. CLEANUP UV LAYERS
            target_uv_name = "UV_Bake"
            
            # Ensure target exists
            target_layer = obj.data.uv_layers.get(target_uv_name)
            if not target_layer:
                self.report({'WARNING'}, "Bake UV missing, creating default.")
                target_layer = obj.data.uv_layers.new(name=target_uv_name)
            
            # Collect names to remove (Safety first: iterate names, not objects)
            names_to_remove = [ul.name for ul in obj.data.uv_layers if ul.name != target_uv_name]
            
            for name in names_to_remove:
                l = obj.data.uv_layers.get(name)
                if l:
                    obj.data.uv_layers.remove(l)
                
            # Set Active
            target_layer = obj.data.uv_layers.get(target_uv_name)
            if target_layer:
                target_layer.active = True
                target_layer.active_render = True
                obj.data.uv_layers.active_index = 0 # Force index 0
            
            self.report({'INFO'}, "Bake complete & Material assigned.")
            
            # FIX: Force MATERIAL Preview so user sees the baked result
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.shading.type = 'MATERIAL'
            
        except Exception as e:
            self.report({'ERROR'}, f"Bake failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
        
        return {'FINISHED'}
