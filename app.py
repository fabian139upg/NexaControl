from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
import sqlite3, os, json, secrets, mimetypes
from functools import wraps
from datetime import datetime
from pathlib import Path
import hashlib, hmac
from werkzeug.utils import secure_filename
from openpyxl import Workbook
from io import BytesIO

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'nexacontrol.db'
UPLOAD_DIR = BASE_DIR / 'uploads' / 'evidencias'
ALLOWED_EXTENSIONS = {'pdf','png','jpg','jpeg','webp','txt','csv','doc','docx','xls','xlsx'}
MAX_FILE_SIZE = 20 * 1024 * 1024

def generate_password_hash(password):
    salt=secrets.token_hex(16)
    rounds=260000
    digest=hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), rounds).hex()
    return f"pbkdf2_sha256${rounds}${salt}${digest}"

def check_password_hash(stored,password):
    try:
        algo,rounds,salt,digest=stored.split('$',3)
        if algo!='pbkdf2_sha256': return False
        calc=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),int(rounds)).hex()
        return hmac.compare_digest(calc,digest)
    except Exception:
        return False

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'nexacontrol-dev-change-me')
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def db():
    con=sqlite3.connect(DB_PATH)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con

def qone(sql, params=()):
    con=db(); row=con.execute(sql,params).fetchone(); con.close(); return row

def qall(sql, params=()):
    con=db(); rows=con.execute(sql,params).fetchall(); con.close(); return rows

def execute(sql, params=()):
    con=db(); cur=con.execute(sql,params); con.commit(); rid=cur.lastrowid; con.close(); return rid

def log_activity(action, description=''):
    if session.get('user_id'):
        execute('INSERT INTO actividad_usuario(usuario_id,accion,descripcion,ip) VALUES(?,?,?,?)',
                (session['user_id'], action, description, request.remote_addr))

def login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not session.get('user_id'): return redirect(url_for('login'))
        return fn(*a,**kw)
    return wrapper

def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a,**kw):
            if not session.get('user_id'): return redirect(url_for('login'))
            if session.get('role') not in roles: abort(403)
            return fn(*a,**kw)
        return wrapper
    return deco

def csrf_token():
    if '_csrf' not in session: session['_csrf']=secrets.token_hex(24)
    return session['_csrf']
app.jinja_env.globals['csrf_token']=csrf_token

def verify_csrf():
    if request.form.get('_csrf') != session.get('_csrf'): abort(400, 'Token CSRF inválido')

def allowed_file(name):
    return '.' in name and name.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def nav_for(role):
    common=[]
    if role=='administrador':
        return [('dashboard','Dashboard','⌂'),('clients','Clientes','◉'),('users','Usuarios','◎'),('requirements','Requisitos','▤'),('evidences','Evidencias','▣'),('reports','Reportes','▥'),('settings','Configuración','⚙')]
    if role=='auditor':
        return [('dashboard','Dashboard','⌂'),('clients','Clientes','◉'),('evidences','Evidencias','▣'),('findings','Hallazgos','△'),('plans','Planes','◇'),('reports','Reportes','▥')]
    return [('dashboard','Dashboard','⌂'),('requirements','Requisitos','▤'),('evidences','Mis evidencias','▣'),('findings','Hallazgos','△'),('plans','Planes','◇'),('reports','Mi reporte','▥')]
app.jinja_env.globals['nav_for']=nav_for

@app.route('/', methods=['GET'])
def index():
    if not session.get('user_id'): return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET','POST'])
def login():
    if session.get('user_id'): return redirect(url_for('dashboard'))
    if request.method=='POST':
        email=request.form.get('correo','').strip().lower(); password=request.form.get('password','')
        u=qone('''SELECT u.*,r.nombre rol,c.nombre cliente FROM usuarios u JOIN roles r ON r.id=u.rol_id LEFT JOIN clientes c ON c.id=u.cliente_id WHERE lower(u.correo)=?''',(email,))
        if u and u['activo'] and check_password_hash(u['password'],password):
            session.clear(); session.update(user_id=u['id'],client_id=u['cliente_id'],name=u['nombre'],email=u['correo'],role=u['rol'])
            execute('UPDATE usuarios SET ultimo_acceso=CURRENT_TIMESTAMP WHERE id=?',(u['id'],))
            log_activity('LOGIN','Inicio de sesión')
            return redirect(url_for('dashboard'))
        flash('Correo o contraseña incorrectos.','error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    if session.get('user_id'): log_activity('LOGOUT','Cierre de sesión')
    session.clear(); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    role=session['role']; cid=session.get('client_id')
    con=db()
    total_req=con.execute('SELECT COUNT(*) n FROM requisitos WHERE activo=1').fetchone()['n']
    total_clients=con.execute('SELECT COUNT(*) n FROM clientes WHERE activo=1').fetchone()['n']
    if role=='cliente':
        evid=con.execute('SELECT COUNT(*) n FROM evidencias WHERE cliente_id=? AND activo=1',(cid,)).fetchone()['n']
        hall=con.execute("SELECT COUNT(*) n FROM hallazgos WHERE cliente_id=? AND estado IN ('ABIERTO','EN_PROCESO')",(cid,)).fetchone()['n']
        evaluated=con.execute('''SELECT COUNT(DISTINCT ev.requisito_id) n FROM evaluaciones ev JOIN evidencias e ON e.id=ev.evidencia_id WHERE e.cliente_id=? AND e.activo=1''',(cid,)).fetchone()['n']
        matrices=con.execute('''SELECT m.codigo,m.nombre,COUNT(DISTINCT r.id) total,COUNT(DISTINCT ev.requisito_id) evaluados FROM matrices m LEFT JOIN requisitos r ON r.matriz_id=m.id AND r.activo=1 LEFT JOIN evidencias e ON e.requisito_id=r.id AND e.cliente_id=? AND e.activo=1 LEFT JOIN evaluaciones ev ON ev.evidencia_id=e.id WHERE m.activo=1 GROUP BY m.id ORDER BY m.id''',(cid,)).fetchall()
    else:
        evid=con.execute('SELECT COUNT(*) n FROM evidencias WHERE activo=1').fetchone()['n']
        hall=con.execute("SELECT COUNT(*) n FROM hallazgos WHERE estado IN ('ABIERTO','EN_PROCESO')").fetchone()['n']
        evaluated=con.execute('SELECT COUNT(DISTINCT requisito_id) n FROM evaluaciones').fetchone()['n']
        matrices=con.execute('''SELECT m.codigo,m.nombre,COUNT(DISTINCT r.id) total,COUNT(DISTINCT ev.requisito_id) evaluados FROM matrices m LEFT JOIN requisitos r ON r.matriz_id=m.id AND r.activo=1 LEFT JOIN evaluaciones ev ON ev.requisito_id=r.id WHERE m.activo=1 GROUP BY m.id ORDER BY m.id''').fetchall()
    con.close()
    return render_template('dashboard.html', total_req=total_req,total_clients=total_clients,evid=evid,hall=hall,evaluated=evaluated,matrices=matrices)

@app.route('/clientes', methods=['GET','POST'])
@role_required('administrador','auditor')
def clients():
    if request.method=='POST':
        if session['role']!='administrador': abort(403)
        verify_csrf(); action=request.form.get('action')
        if action in ('create','edit'):
            vals=(request.form.get('nombre','').strip(),request.form.get('razon_social','').strip(),request.form.get('rfc','').strip(),request.form.get('correo','').strip(),request.form.get('telefono','').strip())
            if not vals[0]: flash('El nombre es obligatorio.','error')
            elif action=='create': execute('INSERT INTO clientes(nombre,razon_social,rfc,correo,telefono) VALUES(?,?,?,?,?)',vals); flash('Cliente creado.','ok')
            else: execute('UPDATE clientes SET nombre=?,razon_social=?,rfc=?,correo=?,telefono=? WHERE id=?',vals+(int(request.form['id']),)); flash('Cliente actualizado.','ok')
        elif action=='toggle': execute('UPDATE clientes SET activo=CASE activo WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(int(request.form['id']),)); flash('Estado actualizado.','ok')
        return redirect(url_for('clients'))
    rows=qall('''SELECT c.*, (SELECT COUNT(*) FROM usuarios u WHERE u.cliente_id=c.id) usuarios,(SELECT COUNT(*) FROM evidencias e WHERE e.cliente_id=c.id) evidencias,(SELECT COUNT(*) FROM hallazgos h WHERE h.cliente_id=c.id) hallazgos FROM clientes c ORDER BY c.id DESC''')
    edit=qone('SELECT * FROM clientes WHERE id=?',(request.args.get('edit'),)) if request.args.get('edit') else None
    return render_template('clients.html',rows=rows,edit=edit)

@app.route('/usuarios', methods=['GET','POST'])
@role_required('administrador')
def users():
    if request.method=='POST':
        verify_csrf(); action=request.form.get('action'); uid=int(request.form.get('id') or 0)
        try:
            if action in ('create','edit'):
                nombre=request.form.get('nombre','').strip(); correo=request.form.get('correo','').strip().lower(); rid=int(request.form.get('rol_id') or 0); cid=request.form.get('cliente_id') or None; pwd=request.form.get('password','')
                if not nombre or not correo or not rid: raise ValueError('Completa nombre, correo y rol.')
                if action=='create':
                    if len(pwd)<8: raise ValueError('La contraseña debe tener mínimo 8 caracteres.')
                    execute('INSERT INTO usuarios(cliente_id,rol_id,nombre,correo,password) VALUES(?,?,?,?,?)',(cid,rid,nombre,correo,generate_password_hash(pwd)))
                else:
                    if pwd:
                        if len(pwd)<8: raise ValueError('La contraseña debe tener mínimo 8 caracteres.')
                        execute('UPDATE usuarios SET cliente_id=?,rol_id=?,nombre=?,correo=?,password=? WHERE id=?',(cid,rid,nombre,correo,generate_password_hash(pwd),uid))
                    else: execute('UPDATE usuarios SET cliente_id=?,rol_id=?,nombre=?,correo=? WHERE id=?',(cid,rid,nombre,correo,uid))
                flash('Usuario guardado.','ok')
            elif action=='toggle':
                if uid==session['user_id']: raise ValueError('No puedes desactivar tu propia cuenta.')
                execute('UPDATE usuarios SET activo=CASE activo WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(uid,)); flash('Estado actualizado.','ok')
        except (ValueError,sqlite3.IntegrityError) as ex: flash(str(ex),'error')
        return redirect(url_for('users'))
    rows=qall('''SELECT u.*,r.nombre rol,c.nombre cliente FROM usuarios u JOIN roles r ON r.id=u.rol_id LEFT JOIN clientes c ON c.id=u.cliente_id ORDER BY u.id DESC''')
    edit=qone('SELECT * FROM usuarios WHERE id=?',(request.args.get('edit'),)) if request.args.get('edit') else None
    return render_template('users.html',rows=rows,edit=edit,roles=qall('SELECT * FROM roles'),clients=qall('SELECT * FROM clientes WHERE activo=1 ORDER BY nombre'))

@app.route('/requisitos')
@login_required
def requirements():
    code=request.args.get('matriz',''); cid=session.get('client_id')
    sql='''SELECT r.id,m.codigo,m.nombre matriz,r.numero,r.titulo,r.descripcion,(SELECT COUNT(*) FROM subrequisitos s WHERE s.requisito_id=r.id AND s.activo=1) subs'''
    params=[]
    if session['role']=='cliente':
        sql+=",(SELECT COUNT(*) FROM evidencias e WHERE e.requisito_id=r.id AND e.cliente_id=? AND e.activo=1) entregadas"; params.append(cid)
    else: sql+=",(SELECT COUNT(*) FROM evidencias e WHERE e.requisito_id=r.id AND e.activo=1) entregadas"
    sql+=' FROM requisitos r JOIN matrices m ON m.id=r.matriz_id WHERE r.activo=1 AND m.activo=1'
    if code: sql+=' AND m.codigo=?'; params.append(code)
    sql+=' ORDER BY m.id,r.id'
    return render_template('requirements.html',rows=qall(sql,params),matrices=qall('SELECT * FROM matrices WHERE activo=1 ORDER BY id'),code=code)

@app.route('/requisito/<int:rid>', methods=['GET','POST'])
@login_required
def requirement_detail(rid):
    req=qone('''SELECT r.*,m.codigo matriz_codigo,m.nombre matriz_nombre FROM requisitos r JOIN matrices m ON m.id=r.matriz_id WHERE r.id=? AND r.activo=1''',(rid,))
    if not req: abort(404)
    if request.method=='POST':
        if session['role']!='cliente': abort(403)
        verify_csrf(); f=request.files.get('archivo')
        if not f or not f.filename or not allowed_file(f.filename): flash('Archivo no permitido.','error')
        else:
            ext=f.filename.rsplit('.',1)[1].lower(); stored=f"{datetime.now():%Y%m%d%H%M%S}_{secrets.token_hex(5)}.{ext}"; path=UPLOAD_DIR/stored; f.save(path)
            execute('''INSERT INTO evidencias(cliente_id,requisito_id,subrequisito_id,usuario_id,nombre_original,nombre_archivo,ruta_archivo,extension,tipo_mime,tamanio,comentario) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(session['client_id'],rid,request.form.get('subrequisito_id') or None,session['user_id'],secure_filename(f.filename),stored,str(path.relative_to(BASE_DIR)),ext,f.mimetype,path.stat().st_size,request.form.get('comentario','').strip()))
            log_activity('UPLOAD',f'Evidencia requisito {rid}'); flash('Evidencia cargada correctamente.','ok')
        return redirect(url_for('requirement_detail',rid=rid))
    subs=qall('SELECT * FROM subrequisitos WHERE requisito_id=? AND activo=1 ORDER BY id',(rid,))
    reqev=qall('SELECT * FROM evidencias_requeridas WHERE requisito_id=? ORDER BY id',(rid,))
    crit=qall('SELECT * FROM criterios_evaluacion WHERE requisito_id=? ORDER BY id',(rid,))
    evid=[]
    if session['role']=='cliente': evid=qall('SELECT * FROM evidencias WHERE requisito_id=? AND cliente_id=? AND activo=1 ORDER BY fecha_subida DESC',(rid,session['client_id']))
    return render_template('requirement_detail.html',r=req,subs=subs,reqev=reqev,crit=crit,evid=evid)

@app.route('/evidencias')
@login_required
def evidences():
    params=[]
    sql='''SELECT e.*,c.nombre cliente,m.codigo,r.numero,r.titulo, s.codigo subcodigo, ee.nombre estado,ev.comentario comentario_auditor FROM evidencias e JOIN clientes c ON c.id=e.cliente_id LEFT JOIN requisitos r ON r.id=e.requisito_id LEFT JOIN matrices m ON m.id=r.matriz_id LEFT JOIN subrequisitos s ON s.id=e.subrequisito_id LEFT JOIN evaluaciones ev ON ev.id=(SELECT ev2.id FROM evaluaciones ev2 WHERE ev2.evidencia_id=e.id ORDER BY ev2.id DESC LIMIT 1) LEFT JOIN estados_evaluacion ee ON ee.id=ev.estado_id WHERE e.activo=1'''
    if session['role']=='cliente': sql+=' AND e.cliente_id=?'; params.append(session['client_id'])
    elif request.args.get('cliente_id'): sql+=' AND e.cliente_id=?'; params.append(int(request.args['cliente_id']))
    sql+=' ORDER BY e.fecha_subida DESC'
    return render_template('evidences.html',rows=qall(sql,params),clients=qall('SELECT * FROM clientes WHERE activo=1 ORDER BY nombre'))

def get_evidence_or_404(eid):
    e=qone('SELECT * FROM evidencias WHERE id=? AND activo=1',(eid,))
    if not e: abort(404)
    if session['role']=='cliente' and e['cliente_id']!=session['client_id']: abort(403)
    return e

@app.route('/evidencia/<int:eid>/preview')
@login_required
def preview_evidence(eid):
    e=get_evidence_or_404(eid); path=BASE_DIR/e['ruta_archivo']
    if not path.exists(): abort(404)
    mime=e['tipo_mime'] or mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    if not (mime.startswith('image/') or mime=='application/pdf' or mime.startswith('text/')): flash('Este tipo de archivo no puede mostrarse en el navegador; puedes descargarlo.','error'); return redirect(url_for('evidences'))
    return send_file(path,mimetype=mime,as_attachment=False,download_name=e['nombre_original'])

@app.route('/evidencia/<int:eid>/download')
@login_required
def download_evidence(eid):
    e=get_evidence_or_404(eid); path=BASE_DIR/e['ruta_archivo']
    if not path.exists(): abort(404)
    return send_file(path,as_attachment=True,download_name=e['nombre_original'])

@app.route('/evidencia/<int:eid>/evaluar', methods=['GET','POST'])
@role_required('auditor','administrador')
def evaluate(eid):
    e=qone('''SELECT e.*,c.nombre cliente,m.codigo matriz,r.numero,r.titulo,r.descripcion requisito FROM evidencias e JOIN clientes c ON c.id=e.cliente_id LEFT JOIN requisitos r ON r.id=e.requisito_id LEFT JOIN matrices m ON m.id=r.matriz_id WHERE e.id=? AND e.activo=1''',(eid,))
    if not e: abort(404)
    actual=qone('SELECT * FROM evaluaciones WHERE evidencia_id=? ORDER BY id DESC LIMIT 1',(eid,))
    if request.method=='POST':
        verify_csrf(); estado=int(request.form.get('estado_id') or 0); comment=request.form.get('comentario','').strip()
        con=db()
        try:
            if actual:
                old=actual['estado_id']; con.execute('UPDATE evaluaciones SET estado_id=?,comentario=?,auditor_id=?,actualizada=CURRENT_TIMESTAMP WHERE id=?',(estado,comment,session['user_id'],actual['id'])); eval_id=actual['id']
            else:
                old=None; cur=con.execute('INSERT INTO evaluaciones(evidencia_id,requisito_id,subrequisito_id,auditor_id,estado_id,comentario) VALUES(?,?,?,?,?,?)',(eid,e['requisito_id'],e['subrequisito_id'],session['user_id'],estado,comment)); eval_id=cur.lastrowid
            con.execute('INSERT INTO historial_evaluaciones(evaluacion_id,estado_anterior,estado_nuevo,usuario_id,comentario) VALUES(?,?,?,?,?)',(eval_id,old,estado,session['user_id'],comment)); con.commit(); flash('Evaluación guardada.','ok')
        finally: con.close()
        return redirect(url_for('evidences',cliente_id=e['cliente_id']))
    return render_template('evaluate.html',e=e,actual=actual,states=qall('SELECT * FROM estados_evaluacion ORDER BY id'))

@app.route('/hallazgos', methods=['GET','POST'])
@login_required
def findings():
    cid=session.get('client_id') if session['role']=='cliente' else (int(request.args.get('cliente_id')) if request.args.get('cliente_id') else None)
    if request.method=='POST':
        if session['role'] not in ('auditor','administrador'): abort(403)
        verify_csrf(); cid=int(request.form['cliente_id'])
        execute('''INSERT INTO hallazgos(cliente_id,requisito_id,creado_por,titulo,descripcion,severidad,estado,fecha_limite) VALUES(?,?,?,?,?,?,?,?)''',(cid,request.form.get('requisito_id') or None,session['user_id'],request.form['titulo'].strip(),request.form['descripcion'].strip(),request.form.get('severidad','MEDIO'),'ABIERTO',request.form.get('fecha_limite') or None)); flash('Hallazgo creado.','ok')
        return redirect(url_for('findings',cliente_id=cid))
    sql='''SELECT h.*,c.nombre cliente,m.codigo,r.numero FROM hallazgos h JOIN clientes c ON c.id=h.cliente_id LEFT JOIN requisitos r ON r.id=h.requisito_id LEFT JOIN matrices m ON m.id=r.matriz_id'''; params=[]
    if cid: sql+=' WHERE h.cliente_id=?'; params.append(cid)
    sql+=' ORDER BY h.id DESC'
    return render_template('findings.html',rows=qall(sql,params),clients=qall('SELECT * FROM clientes WHERE activo=1 ORDER BY nombre'),requirements=qall('''SELECT r.id,m.codigo,r.numero,r.titulo FROM requisitos r JOIN matrices m ON m.id=r.matriz_id WHERE r.activo=1 ORDER BY m.id,r.id'''),selected_client=cid)

@app.route('/planes', methods=['GET','POST'])
@login_required
def plans():
    if request.method=='POST':
        if session['role'] not in ('auditor','administrador'): abort(403)
        verify_csrf(); execute('''INSERT INTO planes_remediacion(hallazgo_id,accion,fecha_inicio,fecha_limite,estado,comentarios) VALUES(?,?,?,?,?,?)''',(int(request.form['hallazgo_id']),request.form['accion'].strip(),request.form.get('fecha_inicio') or None,request.form.get('fecha_limite') or None,request.form.get('estado','PENDIENTE'),request.form.get('comentarios','').strip())); flash('Plan guardado.','ok'); return redirect(url_for('plans'))
    sql='''SELECT p.*,h.titulo hallazgo,c.nombre cliente FROM planes_remediacion p JOIN hallazgos h ON h.id=p.hallazgo_id JOIN clientes c ON c.id=h.cliente_id'''; params=[]
    if session['role']=='cliente': sql+=' WHERE h.cliente_id=?'; params.append(session['client_id'])
    sql+=' ORDER BY p.id DESC'
    hall=qall("SELECT h.id,h.titulo,c.nombre cliente FROM hallazgos h JOIN clientes c ON c.id=h.cliente_id WHERE h.estado!='CERRADO' ORDER BY h.id DESC")
    return render_template('plans.html',rows=qall(sql,params),findings=hall)

@app.route('/reportes')
@login_required
def reports():
    clients=qall('SELECT * FROM clientes WHERE activo=1 ORDER BY nombre')
    return render_template('reports.html',clients=clients)

@app.route('/reporte/excel')
@login_required
def report_excel():
    cid=session['client_id'] if session['role']=='cliente' else int(request.args.get('cliente_id') or 0)
    if not cid: flash('Selecciona un cliente.','error'); return redirect(url_for('reports'))
    c=qone('SELECT * FROM clientes WHERE id=?',(cid,));
    if not c: abort(404)
    results=qall('''SELECT m.codigo,r.numero,r.titulo,ee.nombre estado,ev.comentario FROM evaluaciones ev JOIN evidencias e ON e.id=ev.evidencia_id JOIN requisitos r ON r.id=ev.requisito_id JOIN matrices m ON m.id=r.matriz_id JOIN estados_evaluacion ee ON ee.id=ev.estado_id WHERE e.cliente_id=? ORDER BY m.id,r.id''',(cid,))
    halls=qall('SELECT titulo,severidad,estado,fecha_limite FROM hallazgos WHERE cliente_id=? ORDER BY id DESC',(cid,))
    wb=Workbook(); ws=wb.active; ws.title='Evaluaciones'; ws.append(['Cliente',c['nombre']]); ws.append([]); ws.append(['Matriz','No.','Requisito','Estado','Comentario'])
    for r in results: ws.append([r['codigo'],r['numero'],r['titulo'],r['estado'],r['comentario']])
    hs=wb.create_sheet('Hallazgos'); hs.append(['Título','Severidad','Estado','Fecha límite'])
    for h in halls: hs.append([h['titulo'],h['severidad'],h['estado'],h['fecha_limite']])
    bio=BytesIO(); wb.save(bio); bio.seek(0)
    return send_file(bio,as_attachment=True,download_name=f"reporte_{secure_filename(c['nombre'])}.xlsx",mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/configuracion')
@role_required('administrador')
def settings():
    return render_template('settings.html',python_version=os.sys.version.split()[0],db_path=str(DB_PATH),req_count=qone('SELECT COUNT(*) n FROM requisitos')['n'],activity=qall('''SELECT a.*,u.nombre FROM actividad_usuario a LEFT JOIN usuarios u ON u.id=a.usuario_id ORDER BY a.id DESC LIMIT 20'''))

@app.errorhandler(403)
def forbidden(e): return render_template('error.html',code=403,message='No tienes permiso para acceder a esta sección.'),403
@app.errorhandler(404)
def notfound(e): return render_template('error.html',code=404,message='No se encontró el recurso solicitado.'),404

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)
