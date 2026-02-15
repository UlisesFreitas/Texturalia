import bpy

class TEXTURALIA_PT_debug(bpy.types.Panel):
    bl_label = "Debug"
    bl_idname = "TEXTURALIA_PT_debug"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Texturalia'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 0 # Ensure it's at the top if possible

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Developer Tools", icon='PREFERENCES')
        box.operator("script.reload", text="Reload Scripts", icon='FILE_REFRESH')
        box.operator("outliner.orphans_purge", text="Purge Unused Data", icon='BRUSH_DATA')

class TEXTURALIA_PT_main(bpy.types.Panel):
    bl_label = "Texturalia"
    bl_idname = "TEXTURALIA_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Texturalia'
    bl_order = 1 # Force main panel below debug

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        box = layout.box()
        box.label(text="Step 1: Setup")
        box.operator("texturalia.create_rig", text="Create Rig & Init")
        box.operator("texturalia.cleanup", text="Cleanup")
        
        layout.separator()
        
        box = layout.box()
        row = box.row()
        row.label(text="Step 2: Views")
        row.operator("texturalia.create_default_views", text="", icon='PRESET')
        row.operator("texturalia.add_view", text="", icon='ADD')
        
        if len(scene.texturalia_views) > 0:
            for i, view in enumerate(scene.texturalia_views):
                row = box.row()
                icon = 'TRIA_DOWN' if view.ui_expanded else 'TRIA_RIGHT'
                row.prop(view, "ui_expanded", icon=icon, icon_only=True, emboss=False)
                row.prop(view, "is_active_camera", text="", icon='CAMERA_DATA' if view.is_active_camera else 'OUTLINER_DATA_CAMERA')
                row.prop(view, "name", text="")
                op = row.operator("texturalia.remove_view", text="", icon='X')
                op.view_index = i
                
                if view.ui_expanded:
                    col = box.column(align=True)
                    col.use_property_split = True
                    col.use_property_decorate = False
                    col.prop(view, "view_type")
                    if view.view_type == 'ORBIT':
                        col.prop(view, "orbit_angle")
                    col.prop(view, "orbit_distance")
                    col.prop(view, "target_height")
                    col.prop(view, "camera_height")
                    col.prop(view, "camera_type")
                    if view.camera_type == 'ORTHO':
                        col.prop(view, "camera_zoom")
                    else:
                        col.label(text="Lens: 50mm")
                    col.prop(view, "light_power")
                    
                    row = col.row(align=True)
                    cap_op = row.operator("texturalia.capture_view", text="Capture", icon='RENDER_STILL')
                    cap_op.view_index = i
                    
                    if view.image_ref:
                        view_op = row.operator("texturalia.view_image", text="", icon='IMAGE_DATA')
                        view_op.view_index = i
                    else:
                         row.label(text="", icon='BLANK1')

        layout.separator()
        
        box = layout.box()
        box.label(text="Step 3: Finish")
        box.operator("texturalia.create_live_shader", text="Update Live Preview", icon='SHADING_RENDERED')
        box.operator("texturalia.bake_texture", text="Bake Texture", icon='TEXTURE')
        
        layout.separator()
        
        box = layout.box()
        box.label(text="AI Enhance")
        box.operator("texturalia.enhance_view", text="Enhance Active View", icon='LIGHT')
        
        # Generation Mode (Phase 2)
        # We need to access the active view to set its mode
        active_view = None
        for v in scene.texturalia_views:
            if v.is_active_camera:
                active_view = v
                break

        
        # Fallback: If no active view but views exist, use first one
        if not active_view and len(scene.texturalia_views) > 0:
             active_view = scene.texturalia_views[0]
        
        if active_view:
             # Mode Toggle
             # Enhanced Settings
             col = box.column(align=True)
             col.prop(active_view, "enhance_prompt", text="Prompt")
             col.prop(active_view, "enhance_negative", text="Negative")
             col.prop(active_view, "enhance_denoise", slider=True)
             box.separator()
             
             row = box.row()
             row.label(text=f"Gen Mode ({active_view.name}):")
             row.prop(active_view, "generation_mode", expand=True)
             
             if active_view.generation_mode == 'INPAINT':
                 # Inpaint Tools
                 box.separator()
                 box.label(text="Masking Tools:", icon='BRUSH_DATA')
                 
                 row = box.row()
                 row.operator("texturalia.setup_mask", text="Paint Mask", icon='BRUSH_DATA')
                 row.operator("texturalia.clear_mask", text="Clear", icon='X')
                 
                 row = box.row()
                 row.operator("texturalia.save_mask", text="Save Mask", icon='FILE_TICK')
                 
                 # Brush Settings
                 # Prioritize ACTIVE brush as that's what user is painting with
                 ts = context.tool_settings
                 brush = None
                 if hasattr(ts, "image_paint") and ts.image_paint.brush:
                     brush = ts.image_paint.brush
                 
                 # Only if no active brush, fallback to our specific one (unlikely)
                 if not brush:
                     brush = bpy.data.brushes.get("Texturalia_Mask_Brush")
                 
                 if brush:
                     col = box.column(align=True)
                     col.prop(brush, "size", text="Size")
                     col.prop(brush, "strength", slider=True)
                 else:
                     if active_view.generation_mode == 'INPAINT':
                         box.label(text="Click 'Paint Mask' to init brush", icon='INFO')
        else:
             box.label(text="No Views found. Create Rig first.", icon='ERROR')
        
        wf = scene.texturalia_workflow
        
        # Workflow Selection
        row = box.row()
        row.prop(wf, "workflow_name", text="")
        row.operator("texturalia.load_workflow", text="", icon='IMPORT')
        
        # Manual File Selection (Fallback)
        row = box.row()
        row.prop(wf, "workflow_file", text="Custom File")
        
        # Dynamic Parameters
        if len(wf.node_params) > 0:
            # Grouping Logic
            current_group = None
            group_box = None
            
            for param in wf.node_params:
                # Start new group box if needed
                if param.node_group != current_group:
                    current_group = param.node_group
                    group_box = box.box()
                    group_box.label(text=current_group, icon='NODE')
                
                # Draw Param
                if group_box:
                    col = group_box.column(align=True)
                    if param.value_type == 'INT':
                        col.prop(param, "int_val", text=param.param_name)
                    elif param.value_type == 'FLOAT':
                        col.prop(param, "float_val", text=param.param_name)
                    elif param.value_type == 'FLOAT_FACTOR':
                        col.prop(param, "float_factor", text=param.param_name, slider=True)
                    elif param.value_type == 'STRING':
                        col.prop(param, "str_val", text=param.param_name)
                    elif param.value_type == 'BOOL':
                        col.prop(param, "bool_val", text=param.param_name)
                    elif param.value_type == 'IMAGE':
                        # Image Source Selector
                        sub = col.row(align=True)
                        sub.label(text=param.param_name)
                        sub.prop(param, "image_source", text="")
                        
                        # If Custom, show file selector
                        if param.image_source == 'CUSTOM_FILE':
                            col.prop(param, "image_path", text="")
        
            box.separator()
            
            # Batch Status UI
            if scene.texturalia_is_batching:
                box.label(text=scene.texturalia_batch_status, icon='TIME')
                box.prop(scene, "texturalia_batch_progress", slider=True, text="Progress")
            
            # Action Buttons
            sub = box.row()
            sub.scale_y = 1.5
            
            if scene.texturalia_is_batching:
                 sub.enabled = False
            
            sub.operator("texturalia.enhance_view", text="Generate (Active)", icon='LIGHT')
            sub.operator("texturalia.batch_enhance", text="Generate ALL", icon='SCENE_DATA')
            
        else:
            box.label(text="No workflow loaded. Select & Import above.", icon='INFO')
            sub = box.row()
            sub.enabled = False
            sub.operator("texturalia.enhance_view", text="Generate", icon='LIGHT')

        layout.separator()
        
        # Step 5: Bake
        box = layout.box()
        box.label(text="Step 5: Bake")
        
        # STRICT RULE: Button only active if Preview Mode?
        # "Edit Mode: Todo activado menos bake" implies Bake is DISABLED in Edit Mode.
        row = box.row()
        if is_edit_mode:
            row.enabled = False
            row.label(text="(Enable Preview to Bake)", icon='INFO')
            
        row.operator("texturalia.bake_texture", text="Bake Texture", icon='TEXTURE')


