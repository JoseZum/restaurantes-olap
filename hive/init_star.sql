CREATE DATABASE IF NOT EXISTS restaurantes_dw;
USE restaurantes_dw;

-- Dimensiones

-- 1. Dimensión Tiempo
CREATE TABLE IF NOT EXISTS dim_tiempo (
    tiempo_id             INT,
    fecha                 DATE,
    ano                   INT,
    mes                   INT,
    dia                   INT,
    hora                  INT,
    nombre_mes_completo   STRING,
    dia_semana            STRING
)
STORED AS PARQUET;


-- 2. Dimensión Usuario
CREATE TABLE IF NOT EXISTS dim_usuario (
    usuario_id     INT,
    email          STRING,
    rol            STRING,
    fecha_alta     TIMESTAMP
)
STORED AS PARQUET;

-- 3. Dimensión Restaurante
CREATE TABLE IF NOT EXISTS dim_restaurante (
    restaurante_id INT,
    nombre         STRING,
    categoria      STRING,
    capacidad      INT,
    lat            DOUBLE,
    lon            DOUBLE
)
STORED AS PARQUET;

-- 4. Dimensión Menú / Producto
CREATE TABLE IF NOT EXISTS dim_menu (
    menu_id        INT,
    titulo_menu    STRING,
    categoria_menu STRING,
    activo         BOOLEAN,
    restaurante_id INT
)
STORED AS PARQUET;

-- Tabla de Hechos

CREATE TABLE IF NOT EXISTS hechos_reservas (
    tiempo_id         INT,
    usuario_id        INT,
    restaurante_id    INT,
    menu_id           INT,
    total             DOUBLE,
    estado_reserva    STRING,
    estado_pedido     STRING,
    invitados         INT
)
STORED AS PARQUET;

-- Cubos OLAP / Vistas Agregadas

-- 1. Ingresos por mes y categoría de producto
CREATE VIEW IF NOT EXISTS cubo_ingresos_mes_categoria AS
SELECT 
    t.ano, t.mes, m.categoria_menu,
    SUM(h.total) AS ingresos_total
FROM hechos_reservas h
JOIN dim_tiempo t ON h.tiempo_id = t.tiempo_id
JOIN dim_menu m  ON h.menu_id = m.menu_id
GROUP BY t.ano, t.mes, m.categoria_menu;

-- 2. Actividad de clientes por zona geográfica (lat/lon redondeados a 2 decimales)
CREATE VIEW IF NOT EXISTS cubo_actividad_geo AS
SELECT 
    ROUND(r.lat, 2) AS lat_redondeada,
    ROUND(r.lon, 2) AS lon_redondeada,
    COUNT(DISTINCT h.usuario_id) AS clientes_unicos,
    COUNT(*) AS total_reservas
FROM hechos_reservas h
JOIN dim_restaurante r ON h.restaurante_id = r.restaurante_id
GROUP BY ROUND(r.lat, 2), ROUND(r.lon, 2);

-- 3. Estadísticas de pedidos completados vs cancelados tiempo + estado
CREATE VIEW cubo_estado_pedido_mes AS
SELECT 
    t.ano, t.mes, h.estado_pedido,
    COUNT(*) AS cantidad
FROM hechos_reservas h
JOIN dim_tiempo t ON h.tiempo_id = t.tiempo_id
GROUP BY t.ano, t.mes, h.estado_pedido;

-- 4. Frecuencia de uso de cada producto (menú)
CREATE VIEW IF NOT EXISTS cubo_frecuencia_menu AS
SELECT
    m.titulo_menu,
    COUNT(*) AS veces_pedido
FROM hechos_reservas h
JOIN dim_menu m ON h.menu_id = m.menu_id
GROUP BY m.titulo_menu
ORDER BY veces_pedido DESC;

-- 5. Ingresos totales y reservas por usuario
CREATE VIEW IF NOT EXISTS cubo_usuarios_ingresos AS
SELECT
    u.usuario_id, u.email,
    COUNT(*) AS reservas_hechas,
    SUM(h.total) AS total_gastado
FROM hechos_reservas h
JOIN dim_usuario u ON h.usuario_id = u.usuario_id
GROUP BY u.usuario_id, u.email;
