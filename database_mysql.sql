CREATE DATABASE IF NOT EXISTS nexacontrol
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE nexacontrol;

-- =====================================================
-- ROLES
-- =====================================================

CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);

INSERT INTO roles (nombre, descripcion) VALUES
('administrador', 'Administrador general de la plataforma'),
('auditor', 'Usuario encargado de revisar y evaluar evidencias'),
('cliente', 'Usuario perteneciente al cliente');

-- =====================================================
-- CLIENTES
-- =====================================================

CREATE TABLE clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    razon_social VARCHAR(200),
    rfc VARCHAR(20),
    correo VARCHAR(150),
    telefono VARCHAR(30),
    activo TINYINT(1) DEFAULT 1,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- USUARIOS
-- =====================================================

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NULL,
    rol_id INT NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    correo VARCHAR(150) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    activo TINYINT(1) DEFAULT 1,
    ultimo_acceso DATETIME NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_usuario_cliente
        FOREIGN KEY (cliente_id)
        REFERENCES clientes(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_usuario_rol
        FOREIGN KEY (rol_id)
        REFERENCES roles(id)
);

-- =====================================================
-- MATRICES
-- =====================================================

CREATE TABLE matrices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,
    activo TINYINT(1) DEFAULT 1,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO matrices (codigo, nombre, descripcion) VALUES
('SI', 'Seguridad Informática',
 'Matriz de requisitos de seguridad informática'),

('RO', 'Gestión de Riesgo Operacional',
 'Matriz de gestión de riesgo operacional'),

('PCE', 'Clientes Emisores',
 'Matriz de requerimientos para clientes emisores'),

('IN', 'Interoperabilidad',
 'Matriz de interoperabilidad'),

('RA', 'Riesgos Adicionales',
 'Matriz de riesgos adicionales');

-- =====================================================
-- SECCIONES
-- =====================================================

CREATE TABLE secciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    matriz_id INT NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    area_responsable VARCHAR(255),
    descripcion TEXT,

    CONSTRAINT fk_seccion_matriz
        FOREIGN KEY (matriz_id)
        REFERENCES matrices(id)
        ON DELETE CASCADE
);

-- =====================================================
-- REQUISITOS
-- =====================================================

CREATE TABLE requisitos (
    id INT AUTO_INCREMENT PRIMARY KEY,

    matriz_id INT NOT NULL,
    seccion_id INT NULL,

    numero VARCHAR(50),
    titulo TEXT,
    descripcion TEXT,

    activo TINYINT(1) DEFAULT 1,

    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_requisito_matriz
        FOREIGN KEY (matriz_id)
        REFERENCES matrices(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_requisito_seccion
        FOREIGN KEY (seccion_id)
        REFERENCES secciones(id)
        ON DELETE SET NULL,

    INDEX idx_requisito_matriz (matriz_id),
    INDEX idx_requisito_numero (numero)
);

-- =====================================================
-- SUBREQUISITOS
-- =====================================================

CREATE TABLE subrequisitos (
    id INT AUTO_INCREMENT PRIMARY KEY,

    requisito_id INT NOT NULL,

    codigo VARCHAR(50),
    descripcion TEXT,

    nivel INT DEFAULT 1,

    activo TINYINT(1) DEFAULT 1,

    CONSTRAINT fk_subrequisito_requisito
        FOREIGN KEY (requisito_id)
        REFERENCES requisitos(id)
        ON DELETE CASCADE,

    INDEX idx_subrequisito_requisito (requisito_id)
);

-- =====================================================
-- EVIDENCIAS REQUERIDAS
-- =====================================================

CREATE TABLE evidencias_requeridas (
    id INT AUTO_INCREMENT PRIMARY KEY,

    requisito_id INT NULL,
    subrequisito_id INT NULL,

    descripcion TEXT NOT NULL,

    tipo_archivo VARCHAR(50),

    obligatorio TINYINT(1) DEFAULT 1,

    CONSTRAINT fk_er_requisito
        FOREIGN KEY (requisito_id)
        REFERENCES requisitos(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_er_subrequisito
        FOREIGN KEY (subrequisito_id)
        REFERENCES subrequisitos(id)
        ON DELETE CASCADE
);

-- =====================================================
-- CRITERIOS DE EVALUACIÓN
-- =====================================================

CREATE TABLE criterios_evaluacion (
    id INT AUTO_INCREMENT PRIMARY KEY,

    requisito_id INT NULL,
    subrequisito_id INT NULL,

    descripcion TEXT NOT NULL,

    ponderacion DECIMAL(8,2) DEFAULT 1.00,

    CONSTRAINT fk_criterio_requisito
        FOREIGN KEY (requisito_id)
        REFERENCES requisitos(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_criterio_subrequisito
        FOREIGN KEY (subrequisito_id)
        REFERENCES subrequisitos(id)
        ON DELETE CASCADE
);

-- =====================================================
-- ESTADOS
-- =====================================================

CREATE TABLE estados_evaluacion (
    id INT AUTO_INCREMENT PRIMARY KEY,

    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,

    porcentaje DECIMAL(8,2) NULL,

    color VARCHAR(20)
);

INSERT INTO estados_evaluacion
(codigo, nombre, porcentaje, color)
VALUES
('CUMPLE', 'Cumple', 100.00, 'green'),
('NO_CUMPLE', 'No cumple', 0.00, 'red'),
('CUMPLE_PARCIAL', 'Cumple parcial', 50.00, 'orange'),
('NO_ENTREGADO', 'No entregado', 0.00, 'gray'),
('NO_APLICA', 'No aplica', NULL, 'gray');

-- =====================================================
-- EVIDENCIAS SUBIDAS POR CLIENTE
-- =====================================================

CREATE TABLE evidencias (
    id INT AUTO_INCREMENT PRIMARY KEY,

    cliente_id INT NOT NULL,
    requisito_id INT NULL,
    subrequisito_id INT NULL,

    usuario_id INT NOT NULL,

    nombre_original VARCHAR(255) NOT NULL,
    nombre_archivo VARCHAR(255) NOT NULL,
    ruta_archivo VARCHAR(500) NOT NULL,

    extension VARCHAR(20),
    tipo_mime VARCHAR(100),
    tamanio BIGINT,

    comentario TEXT,

    fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    activo TINYINT(1) DEFAULT 1,

    CONSTRAINT fk_evidencia_cliente
        FOREIGN KEY (cliente_id)
        REFERENCES clientes(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_evidencia_requisito
        FOREIGN KEY (requisito_id)
        REFERENCES requisitos(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_evidencia_subrequisito
        FOREIGN KEY (subrequisito_id)
        REFERENCES subrequisitos(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_evidencia_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
);

-- =====================================================
-- EVALUACIONES DEL AUDITOR
-- =====================================================

CREATE TABLE evaluaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,

    evidencia_id INT NULL,

    requisito_id INT NOT NULL,
    subrequisito_id INT NULL,

    auditor_id INT NOT NULL,

    estado_id INT NOT NULL,

    comentario TEXT,

    fecha_evaluacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    actualizada DATETIME NULL,

    CONSTRAINT fk_evaluacion_evidencia
        FOREIGN KEY (evidencia_id)
        REFERENCES evidencias(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_evaluacion_requisito
        FOREIGN KEY (requisito_id)
        REFERENCES requisitos(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_evaluacion_subrequisito
        FOREIGN KEY (subrequisito_id)
        REFERENCES subrequisitos(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_evaluacion_auditor
        FOREIGN KEY (auditor_id)
        REFERENCES usuarios(id),

    CONSTRAINT fk_evaluacion_estado
        FOREIGN KEY (estado_id)
        REFERENCES estados_evaluacion(id)
);

-- =====================================================
-- HISTORIAL DE EVALUACIONES
-- =====================================================

CREATE TABLE historial_evaluaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,

    evaluacion_id INT NOT NULL,

    estado_anterior INT NULL,
    estado_nuevo INT NOT NULL,

    usuario_id INT NOT NULL,

    comentario TEXT,

    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_historial_evaluacion
        FOREIGN KEY (evaluacion_id)
        REFERENCES evaluaciones(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_historial_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
);

-- =====================================================
-- HALLAZGOS
-- =====================================================

CREATE TABLE hallazgos (
    id INT AUTO_INCREMENT PRIMARY KEY,

    cliente_id INT NOT NULL,

    requisito_id INT NULL,
    subrequisito_id INT NULL,

    creado_por INT NOT NULL,

    titulo VARCHAR(255) NOT NULL,
    descripcion TEXT NOT NULL,

    severidad ENUM(
        'CRITICO',
        'ALTO',
        'MEDIO',
        'BAJO'
    ) DEFAULT 'MEDIO',

    estado ENUM(
        'ABIERTO',
        'EN_PROCESO',
        'CORREGIDO',
        'CERRADO'
    ) DEFAULT 'ABIERTO',

    responsable_id INT NULL,

    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_limite DATE NULL,
    fecha_cierre DATETIME NULL,

    CONSTRAINT fk_hallazgo_cliente
        FOREIGN KEY (cliente_id)
        REFERENCES clientes(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_hallazgo_requisito
        FOREIGN KEY (requisito_id)
        REFERENCES requisitos(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_hallazgo_subrequisito
        FOREIGN KEY (subrequisito_id)
        REFERENCES subrequisitos(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_hallazgo_creador
        FOREIGN KEY (creado_por)
        REFERENCES usuarios(id),

    CONSTRAINT fk_hallazgo_responsable
        FOREIGN KEY (responsable_id)
        REFERENCES usuarios(id)
        ON DELETE SET NULL
);

-- =====================================================
-- PLANES DE REMEDIACIÓN
-- =====================================================

CREATE TABLE planes_remediacion (
    id INT AUTO_INCREMENT PRIMARY KEY,

    hallazgo_id INT NOT NULL,

    accion TEXT NOT NULL,

    responsable_id INT NULL,

    fecha_inicio DATE,
    fecha_limite DATE,

    estado ENUM(
        'PENDIENTE',
        'EN_PROCESO',
        'COMPLETADO',
        'CANCELADO'
    ) DEFAULT 'PENDIENTE',

    comentarios TEXT,

    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_plan_hallazgo
        FOREIGN KEY (hallazgo_id)
        REFERENCES hallazgos(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_plan_responsable
        FOREIGN KEY (responsable_id)
        REFERENCES usuarios(id)
        ON DELETE SET NULL
);

-- =====================================================
-- ACTIVIDAD DEL SISTEMA
-- =====================================================

CREATE TABLE actividad_usuario (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    usuario_id INT NULL,

    accion VARCHAR(100) NOT NULL,

    descripcion TEXT,

    ip VARCHAR(45),

    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_actividad_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE SET NULL
);

-- =====================================================
-- NOTIFICACIONES
-- =====================================================

CREATE TABLE notificaciones (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    usuario_id INT NOT NULL,

    titulo VARCHAR(255) NOT NULL,
    mensaje TEXT,

    tipo VARCHAR(50),

    leida TINYINT(1) DEFAULT 0,

    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_notificacion_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE
);

USE nexacontrol;
CREATE TABLE IF NOT EXISTS hallazgo_evidencias (
 id INT AUTO_INCREMENT PRIMARY KEY,
 hallazgo_id INT NOT NULL,
 evidencia_id INT NOT NULL,
 estado ENUM('PENDIENTE','APROBADA','RECHAZADA') NOT NULL DEFAULT 'PENDIENTE',
 auditor_id INT NULL,
 comentario_auditor TEXT NULL,
 fecha_revision DATETIME NULL,
 fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_hallazgo_evidencia (hallazgo_id,evidencia_id),
 CONSTRAINT fk_he_hallazgo FOREIGN KEY (hallazgo_id) REFERENCES hallazgos(id) ON DELETE CASCADE,
 CONSTRAINT fk_he_evidencia FOREIGN KEY (evidencia_id) REFERENCES evidencias(id) ON DELETE CASCADE,
 CONSTRAINT fk_he_auditor FOREIGN KEY (auditor_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
