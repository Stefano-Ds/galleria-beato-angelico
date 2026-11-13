bl_info = {'name':'Visita galleria con collisioni','author':'Galleria','version':(1,0,0),'blender':(5,1,0),'category':'3D View'}
import bpy, math, time, os
from mathutils import Vector
RADIUS=.28
EYE=1.70

def build_obstacles(context):
    result=[]
    deps=context.evaluated_depsgraph_get()
    for ob in context.scene.objects:
        if ob.type!='MESH' or ob.get('walk_ignore',False):continue
        ev=ob.evaluated_get(deps)
        pts=[ev.matrix_world@Vector(v) for v in ev.bound_box]
        lo=[min(v[i] for v in pts) for i in range(3)]
        hi=[max(v[i] for v in pts) for i in range(3)]
        if hi[2]>.12 and lo[2]<1.80:
            result.append((lo[0],hi[0],lo[1],hi[1]))
    return result

def valid(x,y,boxes):
    # The walkable space is the museum plus its neutral entrance apron.
    for i in range(16):
        t=math.tau*i/16;px=x+RADIUS*math.cos(t);py=y+RADIUS*math.sin(t)
        if not ((-5<=px<=5 and 0<=py<=27) or (-6<=px<=6 and -12<=py<=0) or (-6<=px<=6 and -18<=py<=-12)):
            return False
    for x0,x1,y0,y1 in boxes:
        nx=max(x0,min(x,x1));ny=max(y0,min(y,y1))
        if (x-nx)**2+(y-ny)**2<RADIUS**2:return False
    return True

def move(pos,dx,dy,boxes):
    n=max(1,math.ceil(math.hypot(dx,dy)/.055))
    for _ in range(n):
        if valid(pos.x+dx/n,pos.y,boxes):pos.x+=dx/n
        if valid(pos.x,pos.y+dy/n,boxes):pos.y+=dy/n
    pos.z=EYE
    return pos

class VIEW3D_OT_visita_galleria(bpy.types.Operator):
    bl_idname='view3d.visita_galleria'
    bl_label='Entra nella galleria'
    bl_description='Visita da fuori, con collisioni su muri e arredi. WASD e mouse; Esc per terminare'
    def invoke(self,context,event):
        if context.area.type!='VIEW_3D':return {'CANCELLED'}
        self.area=context.area;self.region=context.region;self.rv=context.space_data.region_3d
        self.pos=Vector((0,-16.5,EYE));self.yaw=0.;self.pitch=0.;self.keys=set()
        self.boxes=build_obstacles(context);self.last=time.perf_counter()
        self.cx=self.region.x+self.region.width//2;self.cy=self.region.y+self.region.height//2
        self.rv.view_perspective='PERSP';context.space_data.overlay.show_overlays=False
        self.timer=context.window_manager.event_timer_add(1/60,window=context.window)
        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set('NONE');context.window.cursor_warp(self.cx,self.cy)
        self.area.header_text_set('VISITA | WASD: cammina | Mouse: guarda | Shift: accelera | Esc: termina')
        self.update_view();return {'RUNNING_MODAL'}
    def update_view(self):
        f=Vector((math.sin(self.yaw)*math.cos(self.pitch),math.cos(self.yaw)*math.cos(self.pitch),math.sin(self.pitch)))
        self.rv.view_rotation=f.to_track_quat('-Z','Y');self.rv.view_distance=0.;self.rv.view_location=self.pos
        self.area.tag_redraw()
    def modal(self,context,event):
        if event.type in {'ESC','RIGHTMOUSE','WINDOW_DEACTIVATE'}:
            context.window_manager.event_timer_remove(self.timer);context.window.cursor_modal_restore();self.area.header_text_set(None)
            return {'FINISHED'}
        if event.type in {'W','A','S','D','LEFT_SHIFT','RIGHT_SHIFT'}:
            if event.value=='PRESS':self.keys.add(event.type)
            elif event.value=='RELEASE':self.keys.discard(event.type)
        elif event.type=='MOUSEMOVE':
            dx=event.mouse_x-self.cx;dy=event.mouse_y-self.cy
            if dx or dy:
                self.yaw+=dx*.0022;self.pitch=max(-1.3,min(1.3,self.pitch+dy*.0022))
                context.window.cursor_warp(self.cx,self.cy);self.update_view()
        elif event.type=='TIMER':
            now=time.perf_counter();dt=min(.05,now-self.last);self.last=now
            f=int('W' in self.keys)-int('S' in self.keys);r=int('D' in self.keys)-int('A' in self.keys)
            if f or r:
                speed=3.5 if {'LEFT_SHIFT','RIGHT_SHIFT'}&self.keys else 1.8
                k=speed*dt/max(1,math.hypot(f,r))
                dx=(math.sin(self.yaw)*f+math.cos(self.yaw)*r)*k
                dy=(math.cos(self.yaw)*f-math.sin(self.yaw)*r)*k
                move(self.pos,dx,dy,self.boxes);self.update_view()
        return {'RUNNING_MODAL'}

class VIEW3D_PT_visita_galleria(bpy.types.Panel):
    bl_label='Visita galleria';bl_idname='VIEW3D_PT_visita_galleria';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Visita'
    def draw(self,context):
        self.layout.operator('view3d.visita_galleria',icon='VIEW_CAMERA')
        self.layout.label(text='WASD + mouse | Esc per uscire')
        self.layout.label(text='Partenza esterna e collisioni attive')

classes=(VIEW3D_OT_visita_galleria,VIEW3D_PT_visita_galleria)
def register():
    for cls in classes:
        old=getattr(bpy.types,cls.__name__,None)
        if old:
            try:bpy.utils.unregister_class(old)
            except RuntimeError:pass
        bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(classes):bpy.utils.unregister_class(cls)

if __name__=='__main__':
    # Launcher: open the neighboring project before registering the visit tools.
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)),'Galleria_Beato_Angelico.blend') if '__file__' in globals() else ''
    if path and os.path.isfile(path) and os.path.normcase(bpy.data.filepath)!=os.path.normcase(path):
        bpy.ops.wm.open_mainfile(filepath=path)
    register()

    def start_visit():
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type=='VIEW_3D':
                    region=next((r for r in area.regions if r.type=='WINDOW'),None)
                    if region:
                        with bpy.context.temp_override(window=window,area=area,region=region):
                            bpy.ops.view3d.visita_galleria('INVOKE_DEFAULT')
                        return None
        return .5
    if not bpy.app.background:
        bpy.app.timers.register(start_visit,first_interval=1.0)
