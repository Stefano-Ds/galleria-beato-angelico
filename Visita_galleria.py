bl_info = {'name':'Visita galleria con collisioni','author':'Galleria','version':(1,0,0),'blender':(5,1,0),'category':'3D View'}
import bpy, math, time, os, json, textwrap
import gpu, blf
from gpu_extras.batch import batch_for_shader
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
        if not ((-5<=px<=5 and 0<=py<=27) or (-4<=px<=4 and -8<=py<=0) or (-4<=px<=4 and -14<=py<=-8)):
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


def timeline_data():
    text=bpy.data.texts.get('Cronologia.json')
    if text:return json.loads(text.as_string())
    path=os.path.join(os.path.dirname(bpy.data.filepath),'Galleria_online','cronologia.json')
    if os.path.isfile(path):
        with open(path,encoding='utf-8') as f:return json.load(f)
    return None

def draw_rect(x,y,w,h,color):
    shader=gpu.shader.from_builtin('UNIFORM_COLOR');shader.bind();shader.uniform_float('color',color)
    batch_for_shader(shader,'TRI_FAN',{'pos':[(x,y),(x+w,y),(x+w,y+h),(x,y+h)]}).draw(shader)

def draw_words(text,x,y,size=14,color=(.38,.24,.16,1),font=0):
    blf.size(font,size);blf.color(font,*color);blf.position(font,x,y,0);blf.draw(font,text)


_TITLE_FONT=None
def timeline_title_font():
    global _TITLE_FONT
    if _TITLE_FONT is not None:return _TITLE_FONT
    try:
        import tempfile
        font=bpy.data.fonts.get('Calligrafia cronologia')
        if font and font.packed_file:
            path=os.path.join(tempfile.gettempdir(),'Galleria_GreatVibes.ttf')
            with open(path,'wb') as f:f.write(font.packed_file.data)
            _TITLE_FONT=blf.load(path)
        else:_TITLE_FONT=0
    except Exception:_TITLE_FONT=0
    return _TITLE_FONT

def draw_card(texture,tile,x,y,size):
    col=tile%4;row=tile//4;u0=col/4;u1=(col+1)/4;v0=1-(row+1)/8;v1=1-row/8
    shader=gpu.shader.from_builtin('IMAGE');shader.bind();shader.uniform_sampler('image',texture)
    batch_for_shader(shader,'TRI_FAN',{'pos':[(x,y),(x+size,y),(x+size,y+size),(x,y+size)],'texCoord':[(u0,v0),(u1,v0),(u1,v1),(u0,v1)]}).draw(shader)

class VIEW3D_OT_visita_galleria(bpy.types.Operator):
    bl_idname='view3d.visita_galleria'
    bl_label='Entra nella galleria'
    bl_description='Visita da fuori, con collisioni su muri e arredi. WASD e mouse; Esc per terminare'
    def invoke(self,context,event):
        if context.area.type!='VIEW_3D':return {'CANCELLED'}
        self.area=context.area;self.region=context.region;self.rv=context.space_data.region_3d
        self.pos=Vector((0,-13.0,EYE));self.yaw=0.;self.pitch=-.10;self.keys=set()
        self.boxes=build_obstacles(context);self.last=time.perf_counter()
        self.chronology=timeline_data();self.timeline_open=False;self.timeline_offset=0.;self.timeline_drag=None;self.ring_entered=None;self.ring_armed=True;self.timeline_texture=None
        self.timeline_handler=bpy.types.SpaceView3D.draw_handler_add(self.draw_timeline,(),'WINDOW','POST_PIXEL')
        self.cx=self.region.x+self.region.width//2;self.cy=self.region.y+self.region.height//2
        self.rv.view_perspective='PERSP';context.space_data.overlay.show_overlays=False
        self.previous_toolbar=context.space_data.show_region_toolbar;self.previous_sidebar=context.space_data.show_region_ui
        context.space_data.show_region_toolbar=False;context.space_data.show_region_ui=False;context.space_data.shading.color_type='TEXTURE'
        self.timer=context.window_manager.event_timer_add(1/60,window=context.window)
        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set('NONE');context.window.cursor_warp(self.cx,self.cy)
        self.area.header_text_set('VISITA | WASD: cammina | Mouse: guarda | Shift: accelera | Esc: termina')
        self.update_view();return {'RUNNING_MODAL'}
    def update_view(self):
        f=Vector((math.sin(self.yaw)*math.cos(self.pitch),math.cos(self.yaw)*math.cos(self.pitch),math.sin(self.pitch)))
        self.rv.view_rotation=f.to_track_quat('-Z','Y');self.rv.view_distance=0.;self.rv.view_location=self.pos
        self.area.tag_redraw()
    def open_timeline(self):
        self.timeline_open=True;self.ring_armed=False;self.ring_entered=None;self.keys.clear()
        bpy.context.window.cursor_modal_restore();self.area.header_text_set('LINEA DEL TEMPO | Trascina o usa frecce / rotella | Esc: torna nella sala');self.area.tag_redraw()
    def close_timeline(self,context):
        self.timeline_open=False;self.timeline_drag=None;self.last=time.perf_counter();context.window.cursor_modal_set('NONE');context.window.cursor_warp(self.cx,self.cy)
        self.area.header_text_set('VISITA | WASD: cammina | Mouse: guarda | Resta 2 secondi nell’anello | Esc: termina');self.area.tag_redraw()
    def draw_timeline(self):
        if not self.timeline_open or not self.chronology:return
        region=next((r for r in self.area.regions if r.type=='WINDOW'),None)
        if not region:return
        w=region.width;h=region.height;size=max(130,min(260,(h-250)/2));step=size+42;mid=h/2
        gpu.state.blend_set('ALPHA')
        for j in range(32):
            t=j/31;color=(.859+(.914-.859)*t,.659+(.882-.659)*t,.557+(.859-.557)*t,1)
            draw_rect(0,j*h/32,w,h/32+1,color)
        for x in range(0,w,170):draw_rect(x,0,1,h,(.45,.30,.20,.07))
        for y in range(0,h,170):draw_rect(0,y,w,1,(.45,.30,.20,.07))
        draw_words('Beato Angelico',24,h-68,40,font=timeline_title_font());draw_words('×',w-45,h-65,26)
        draw_rect(0,mid-1,w,2,(.48,.29,.18,1))
        image=bpy.data.images.get('Cronologia pareti')
        if image and self.timeline_texture is None:self.timeline_texture=gpu.texture.from_image(image)
        maxoff=max(0,len(self.chronology['events'])*step-w+50);self.timeline_offset=max(0,min(maxoff,self.timeline_offset))
        for event in self.chronology['events']:
            x=24+event['id']*step-self.timeline_offset
            if x+size<0 or x>w:continue
            if self.timeline_texture:
                if event['life']:draw_card(self.timeline_texture,event['wallTiles']['life'],x,mid+27,size)
                if event['style']:draw_card(self.timeline_texture,event['wallTiles']['style'],x,mid-27-size,size)
            date_lines=textwrap.wrap(event['date'],width=23)
            for j,line in enumerate(date_lines):
                blf.size(0,12);tw=blf.dimensions(0,line)[0];draw_words(line,x+(size-tw)/2,mid+10+(len(date_lines)-1-j)*15,12)
        draw_words('←',25,22,27);draw_words('→',w-50,22,27);draw_words('Frecce / rotella / trascinamento · Esc per chiudere',80,27,12)
        gpu.state.blend_set('NONE')
    def modal(self,context,event):
        if self.timeline_open and event.type!='WINDOW_DEACTIVATE':
            if event.type in {'ESC','RIGHTMOUSE'} and event.value=='PRESS':self.close_timeline(context);return {'RUNNING_MODAL'}
            if event.type in {'LEFT_ARROW','RIGHT_ARROW','WHEELUPMOUSE','WHEELDOWNMOUSE'} and event.value=='PRESS':
                self.timeline_offset+=180 if event.type in {'RIGHT_ARROW','WHEELDOWNMOUSE'} else -180
            if event.type=='LEFTMOUSE':
                if event.value=='PRESS':
                    x=event.mouse_region_x;y=event.mouse_region_y
                    if x>self.region.width-70 and y>self.region.height-70:self.close_timeline(context)
                    elif y<55 and x<80:self.timeline_offset-=250
                    elif y<55 and x>self.region.width-80:self.timeline_offset+=250
                    else:self.timeline_drag=(x,self.timeline_offset)
                else:self.timeline_drag=None
            if event.type=='MOUSEMOVE' and self.timeline_drag:self.timeline_offset=self.timeline_drag[1]+self.timeline_drag[0]-event.mouse_region_x
            self.area.tag_redraw();return {'RUNNING_MODAL'}
        if event.type in {'ESC','RIGHTMOUSE','WINDOW_DEACTIVATE'}:
            context.window_manager.event_timer_remove(self.timer);context.window.cursor_modal_restore();self.area.header_text_set(None)
            context.space_data.show_region_toolbar=self.previous_toolbar;context.space_data.show_region_ui=self.previous_sidebar
            if self.timeline_handler:bpy.types.SpaceView3D.draw_handler_remove(self.timeline_handler,'WINDOW');self.timeline_handler=None
            return {'FINISHED'}
        if event.type in {'W','A','S','D','LEFT_SHIFT','RIGHT_SHIFT'}:
            if event.value=='PRESS':self.keys.add(event.type)
            elif event.value=='RELEASE':self.keys.discard(event.type)
        elif event.type=='LEFTMOUSE' and event.value=='PRESS':
            direction=self.rv.view_rotation@Vector((0,0,-1));hit=context.scene.ray_cast(context.evaluated_depsgraph_get(),self.pos,direction,distance=9)
            if hit[0] and 'timeline_event' in hit[4]:
                self.open_timeline();self.timeline_offset=int(hit[4]['timeline_event'])*min(302,(self.region.height-190)/2+42)
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
            if self.chronology:
                ring=self.chronology['ring'];inside=math.hypot(self.pos.x-ring['x'],self.pos.y-ring['y'])<=ring['radius']
                if not inside:self.ring_entered=None;self.ring_armed=True
                elif self.ring_armed:
                    if self.ring_entered is None:self.ring_entered=now
                    if now-self.ring_entered>=ring['seconds']:self.open_timeline()
        return {'RUNNING_MODAL'}

class VIEW3D_PT_visita_galleria(bpy.types.Panel):
    bl_label='Visita galleria';bl_idname='VIEW3D_PT_visita_galleria';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Visita'
    def draw(self,context):
        self.layout.operator('view3d.visita_galleria',icon='VIEW_CAMERA')
        self.layout.label(text='WASD + mouse | Esc per uscire')
        self.layout.label(text='Resta 2 secondi nell’anello: linea del tempo')

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
