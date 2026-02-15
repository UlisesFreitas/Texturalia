import bpy
from .operators.setup import TEXTURALIA_OT_create_rig, TEXTURALIA_OT_cleanup
from .operators.view import (
    TEXTURALIA_OT_create_default_views,
    TEXTURALIA_OT_add_view,
    TEXTURALIA_OT_capture_view,
    TEXTURALIA_OT_view_image,
    TEXTURALIA_OT_remove_view,
    TEXTURALIA_OT_set_square_resolution
)
from .operators.bake import TEXTURALIA_OT_create_live_shader, TEXTURALIA_OT_bake_texture
from .operators.comfy import TEXTURALIA_OT_test_connection, TEXTURALIA_OT_enhance_view, TEXTURALIA_OT_batch_enhance
from .operators.workflow import TEXTURALIA_OT_load_workflow


# Keep properties and UI here for Phase 1
import math
import mathutils
from mathutils import Vector
import os

bl_info = {
    "name": "Texturalia",
    "author": "Ulises",
    "version": (2, 4, 4),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Texturalia",
    "description": "Simple Multi-View Capture with Orbit Camera",
    "category": "3D View",
}

# =============================
# PROPERTIES & CALLBACKS (IMPORTED Phase 3)
# =============================
from .properties import TexturaliaView

# =============================
# PREFERENCES (IMPORTED)
# =============================
from .preferences import TexturaliaPreferences, TEXTURALIA_OT_refresh_checkpoints

# =============================
# UI PANEL (IMPORTED Phase 2)
# =============================
# Local import to avoid circular dependency issues if any properties are needed
from .ui.panels import TEXTURALIA_PT_main, TEXTURALIA_PT_debug


# =============================
# REGISTRATION
# =============================

classes = (
    TexturaliaPreferences,
    TEXTURALIA_OT_refresh_checkpoints,
    TexturaliaView,
    TEXTURALIA_OT_create_rig,
    TEXTURALIA_OT_cleanup,
    TEXTURALIA_OT_create_default_views,
    TEXTURALIA_OT_add_view,
    TEXTURALIA_OT_remove_view,
    TEXTURALIA_OT_capture_view,
    TEXTURALIA_OT_view_image,
    TEXTURALIA_OT_set_square_resolution,
    TEXTURALIA_OT_create_live_shader,
    TEXTURALIA_OT_bake_texture,
    TEXTURALIA_OT_test_connection,
    TEXTURALIA_OT_enhance_view,
    TEXTURALIA_OT_batch_enhance,
    TEXTURALIA_OT_load_workflow,
    TEXTURALIA_PT_debug,
    TEXTURALIA_PT_main,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.texturalia_views = bpy.props.CollectionProperty(type=TexturaliaView)

def unregister():
    if hasattr(bpy.types.Scene, "texturalia_views"):
        del bpy.types.Scene.texturalia_views
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()