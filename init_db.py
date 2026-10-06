from pathlib import Path
import sqlite3, json
import hashlib, secrets

def generate_password_hash(password):
    salt=secrets.token_hex(16); rounds=260000
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),rounds).hex()
    return f"pbkdf2_sha256${rounds}${salt}${digest}"
BASE=Path(__file__).resolve().parent
DB=BASE/'instance'/'nexacontrol.db'; DB.parent.mkdir(exist_ok=True)
SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS roles(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT UNIQUE NOT NULL,descripcion TEXT);
CREATE TABLE IF NOT EXISTS clientes(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT NOT NULL,razon_social TEXT,rfc TEXT,correo TEXT,telefono TEXT,activo INTEGER DEFAULT 1,fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY AUTOINCREMENT,cliente_id INTEGER,rol_id INTEGER NOT NULL,nombre TEXT NOT NULL,correo TEXT UNIQUE NOT NULL,password TEXT NOT NULL,activo INTEGER DEFAULT 1,ultimo_acceso TEXT,fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE SET NULL,FOREIGN KEY(rol_id) REFERENCES roles(id));
CREATE TABLE IF NOT EXISTS matrices(id INTEGER PRIMARY KEY AUTOINCREMENT,codigo TEXT UNIQUE NOT NULL,nombre TEXT NOT NULL,descripcion TEXT,activo INTEGER DEFAULT 1,fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS secciones(id INTEGER PRIMARY KEY AUTOINCREMENT,matriz_id INTEGER NOT NULL,nombre TEXT NOT NULL,area_responsable TEXT,descripcion TEXT,FOREIGN KEY(matriz_id) REFERENCES matrices(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS requisitos(id INTEGER PRIMARY KEY AUTOINCREMENT,matriz_id INTEGER NOT NULL,seccion_id INTEGER,numero TEXT,titulo TEXT,descripcion TEXT,activo INTEGER DEFAULT 1,fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(matriz_id) REFERENCES matrices(id) ON DELETE CASCADE,FOREIGN KEY(seccion_id) REFERENCES secciones(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS subrequisitos(id INTEGER PRIMARY KEY AUTOINCREMENT,requisito_id INTEGER NOT NULL,codigo TEXT,descripcion TEXT,nivel INTEGER DEFAULT 1,activo INTEGER DEFAULT 1,FOREIGN KEY(requisito_id) REFERENCES requisitos(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS evidencias_requeridas(id INTEGER PRIMARY KEY AUTOINCREMENT,requisito_id INTEGER,subrequisito_id INTEGER,descripcion TEXT NOT NULL,tipo_archivo TEXT,obligatorio INTEGER DEFAULT 1,FOREIGN KEY(requisito_id) REFERENCES requisitos(id) ON DELETE CASCADE,FOREIGN KEY(subrequisito_id) REFERENCES subrequisitos(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS criterios_evaluacion(id INTEGER PRIMARY KEY AUTOINCREMENT,requisito_id INTEGER,subrequisito_id INTEGER,descripcion TEXT NOT NULL,ponderacion REAL DEFAULT 1,FOREIGN KEY(requisito_id) REFERENCES requisitos(id) ON DELETE CASCADE,FOREIGN KEY(subrequisito_id) REFERENCES subrequisitos(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS estados_evaluacion(id INTEGER PRIMARY KEY AUTOINCREMENT,codigo TEXT UNIQUE NOT NULL,nombre TEXT NOT NULL,porcentaje REAL,color TEXT);
CREATE TABLE IF NOT EXISTS evidencias(id INTEGER PRIMARY KEY AUTOINCREMENT,cliente_id INTEGER NOT NULL,requisito_id INTEGER,subrequisito_id INTEGER,usuario_id INTEGER NOT NULL,nombre_original TEXT NOT NULL,nombre_archivo TEXT NOT NULL,ruta_archivo TEXT NOT NULL,extension TEXT,tipo_mime TEXT,tamanio INTEGER,comentario TEXT,fecha_subida TEXT DEFAULT CURRENT_TIMESTAMP,activo INTEGER DEFAULT 1,FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,FOREIGN KEY(requisito_id) REFERENCES requisitos(id) ON DELETE SET NULL,FOREIGN KEY(subrequisito_id) REFERENCES subrequisitos(id) ON DELETE SET NULL,FOREIGN KEY(usuario_id) REFERENCES usuarios(id));
CREATE TABLE IF NOT EXISTS evaluaciones(id INTEGER PRIMARY KEY AUTOINCREMENT,evidencia_id INTEGER,requisito_id INTEGER NOT NULL,subrequisito_id INTEGER,auditor_id INTEGER NOT NULL,estado_id INTEGER NOT NULL,comentario TEXT,fecha_evaluacion TEXT DEFAULT CURRENT_TIMESTAMP,actualizada TEXT,FOREIGN KEY(evidencia_id) REFERENCES evidencias(id) ON DELETE SET NULL,FOREIGN KEY(requisito_id) REFERENCES requisitos(id) ON DELETE CASCADE,FOREIGN KEY(auditor_id) REFERENCES usuarios(id),FOREIGN KEY(estado_id) REFERENCES estados_evaluacion(id));
CREATE TABLE IF NOT EXISTS historial_evaluaciones(id INTEGER PRIMARY KEY AUTOINCREMENT,evaluacion_id INTEGER NOT NULL,estado_anterior INTEGER,estado_nuevo INTEGER NOT NULL,usuario_id INTEGER NOT NULL,comentario TEXT,fecha TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(evaluacion_id) REFERENCES evaluaciones(id) ON DELETE CASCADE,FOREIGN KEY(usuario_id) REFERENCES usuarios(id));
CREATE TABLE IF NOT EXISTS hallazgos(id INTEGER PRIMARY KEY AUTOINCREMENT,cliente_id INTEGER NOT NULL,requisito_id INTEGER,subrequisito_id INTEGER,creado_por INTEGER NOT NULL,titulo TEXT NOT NULL,descripcion TEXT NOT NULL,severidad TEXT DEFAULT 'MEDIO',estado TEXT DEFAULT 'ABIERTO',responsable_id INTEGER,fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,fecha_limite TEXT,fecha_cierre TEXT,FOREIGN KEY(cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,FOREIGN KEY(requisito_id) REFERENCES requisitos(id) ON DELETE SET NULL,FOREIGN KEY(creado_por) REFERENCES usuarios(id));
CREATE TABLE IF NOT EXISTS planes_remediacion(id INTEGER PRIMARY KEY AUTOINCREMENT,hallazgo_id INTEGER NOT NULL,accion TEXT NOT NULL,responsable_id INTEGER,fecha_inicio TEXT,fecha_limite TEXT,estado TEXT DEFAULT 'PENDIENTE',comentarios TEXT,fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(hallazgo_id) REFERENCES hallazgos(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS actividad_usuario(id INTEGER PRIMARY KEY AUTOINCREMENT,usuario_id INTEGER,accion TEXT NOT NULL,descripcion TEXT,ip TEXT,fecha TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL);
'''
if DB.exists(): DB.unlink()
con=sqlite3.connect(DB); con.execute('PRAGMA foreign_keys=ON'); con.executescript(SCHEMA)
roles=[('administrador','Administrador general'),('auditor','Auditor de cumplimiento'),('cliente','Usuario cliente')]
con.executemany('INSERT INTO roles(nombre,descripcion) VALUES(?,?)',roles)
con.execute("INSERT INTO clientes(nombre,razon_social,rfc,correo,telefono) VALUES('Empresa Demo','Empresa Demo S.A. de C.V.','XAXX010101000','contacto@demo.local','55 0000 0000')")
client_id=con.execute('SELECT id FROM clientes LIMIT 1').fetchone()[0]
rids={r[1]:r[0] for r in con.execute('SELECT id,nombre FROM roles')}
users=[(None,rids['administrador'],'Administrador NexaControl','admin@nexacontrol.local',generate_password_hash('Admin123*')),(None,rids['auditor'],'Auditor Demo','auditor@nexacontrol.local',generate_password_hash('Auditor123*')),(client_id,rids['cliente'],'Cliente Demo','cliente@nexacontrol.local',generate_password_hash('Cliente123*'))]
con.executemany('INSERT INTO usuarios(cliente_id,rol_id,nombre,correo,password) VALUES(?,?,?,?,?)',users)
states=[('CUMPLE','Cumple',100,'green'),('NO_CUMPLE','No cumple',0,'red'),('CUMPLE_PARCIAL','Cumple parcial',50,'orange'),('NO_ENTREGADO','No entregado',0,'gray'),('NO_APLICA','No aplica',None,'gray')]
con.executemany('INSERT INTO estados_evaluacion(codigo,nombre,porcentaje,color) VALUES(?,?,?,?)',states)
names={'SI':'Seguridad Informática','RO':'Gestión de Riesgo Operacional','PCE':'Clientes Emisores','IN':'Interoperabilidad','RA':'Riesgos Adicionales'}
with open(BASE/'data'/'matriz.json',encoding='utf-8') as f: matrix=json.load(f)
for code,items in matrix.items():
    cur=con.execute('INSERT INTO matrices(codigo,nombre,descripcion) VALUES(?,?,?)',(code,names.get(code,code),'Matriz migrada desde el portal original'))
    mid=cur.lastrowid
    bynum={}
    for item in items:
        num=(item.get('numero') or '').strip(); reqtxt=(item.get('requisito') or '').strip(); sub=(item.get('sub') or '').strip(); evid=(item.get('evidencia') or '').strip(); crit=(item.get('criterio') or '').strip(); tipo=(item.get('tipo') or '').strip()
        key=num or f'row-{len(bynum)}'
        if key not in bynum:
            rc=con.execute('INSERT INTO requisitos(matriz_id,numero,titulo,descripcion) VALUES(?,?,?,?)',(mid,num,reqtxt,reqtxt)); bynum[key]=rc.lastrowid
        rid=bynum[key]; sid=None
        if sub:
            sc=con.execute('INSERT INTO subrequisitos(requisito_id,codigo,descripcion) VALUES(?,?,?)',(rid,sub,reqtxt)); sid=sc.lastrowid
        if evid: con.execute('INSERT INTO evidencias_requeridas(requisito_id,subrequisito_id,descripcion,tipo_archivo) VALUES(?,?,?,?)',(rid,sid,evid,tipo))
        if crit: con.execute('INSERT INTO criterios_evaluacion(requisito_id,subrequisito_id,descripcion) VALUES(?,?,?)',(rid,sid,crit))
con.commit(); con.close()
print('Base creada:',DB)
print('Admin: admin@nexacontrol.local / Admin123*')
print('Auditor: auditor@nexacontrol.local / Auditor123*')
print('Cliente: cliente@nexacontrol.local / Cliente123*')
