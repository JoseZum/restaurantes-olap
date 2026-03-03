-- =====================================================
-- CONSULTAS SQL PARA DASHBOARDS DE SUPERSET
-- Data Warehouse de Restaurantes
-- =====================================================

-- =====================================================
-- DASHBOARD 1: INGRESOS POR MES Y CATEGORÍA DE PRODUCTO
-- =====================================================

-- Consulta principal: Ingresos mensuales por categoría
CREATE OR REPLACE VIEW v_ingresos_categoria_mes AS
SELECT 
    dt.anio,
    dt.mes,
    dt.nombre_mes,
    dm.categoria,
    COUNT(fp.id_pedido) as total_pedidos,
    SUM(fp.precio_total) as ingresos_total,
    AVG(fp.precio_total) as ingreso_promedio,
    SUM(fp.cantidad) as cantidad_total
FROM fact_pedidos fp
JOIN dim_tiempo dt ON fp.id_tiempo = dt.id_tiempo
JOIN dim_menu dm ON fp.id_menu = dm.id_menu
WHERE fp.estado = 'completado'
GROUP BY dt.anio, dt.mes, dt.nombre_mes, dm.categoria
ORDER BY dt.anio DESC, dt.mes DESC, ingresos_total DESC;

-- Consulta para tendencia de ingresos por categoría
CREATE OR REPLACE VIEW v_tendencia_ingresos_categoria AS
SELECT 
    dm.categoria,
    dt.anio,
    dt.mes,
    SUM(fp.precio_total) as ingresos_mes,
    LAG(SUM(fp.precio_total), 1) OVER (
        PARTITION BY dm.categoria 
        ORDER BY dt.anio, dt.mes
    ) as ingresos_mes_anterior,
    ROUND(
        ((SUM(fp.precio_total) - LAG(SUM(fp.precio_total), 1) OVER (
            PARTITION BY dm.categoria 
            ORDER BY dt.anio, dt.mes
        )) / NULLIF(LAG(SUM(fp.precio_total), 1) OVER (
            PARTITION BY dm.categoria 
            ORDER BY dt.anio, dt.mes
        ), 0)) * 100, 2
    ) as crecimiento_porcentual
FROM fact_pedidos fp
JOIN dim_tiempo dt ON fp.id_tiempo = dt.id_tiempo
JOIN dim_menu dm ON fp.id_menu = dm.id_menu
WHERE fp.estado = 'completado'
GROUP BY dm.categoria, dt.anio, dt.mes
ORDER BY dm.categoria, dt.anio DESC, dt.mes DESC;

-- Top productos por ingresos
CREATE OR REPLACE VIEW v_top_productos_ingresos AS
SELECT 
    dm.titulo as producto,
    dm.categoria,
    dr.nombre as restaurante,
    COUNT(fp.id_pedido) as total_pedidos,
    SUM(fp.precio_total) as ingresos_total,
    AVG(fp.precio_total) as precio_promedio,
    RANK() OVER (ORDER BY SUM(fp.precio_total) DESC) as ranking
FROM fact_pedidos fp
JOIN dim_menu dm ON fp.id_menu = dm.id_menu
JOIN dim_restaurante dr ON fp.id_restaurante = dr.id_restaurante
WHERE fp.estado = 'completado'
GROUP BY dm.titulo, dm.categoria, dr.nombre
ORDER BY ingresos_total DESC
LIMIT 20;

-- =====================================================
-- DASHBOARD 2: ACTIVIDAD DE CLIENTES POR ZONA GEGRÁFICA
-- =====================================================

-- Consulta principal: Actividad por zona geográfica
CREATE OR REPLACE VIEW v_actividad_zona_geografica AS
SELECT 
    du.ciudad,
    du.pais,
    COUNT(DISTINCT du.id_usuario) as total_clientes,
    COUNT(fp.id_pedido) as total_pedidos,
    SUM(fp.precio_total) as ingresos_zona,
    AVG(fp.precio_total) as ticket_promedio,
    COUNT(fr.id_reserva) as total_reservas,
    ROUND(AVG(CAST(fr.numero_personas AS FLOAT)), 2) as personas_promedio_reserva
FROM dim_usuario du
LEFT JOIN fact_pedidos fp ON du.id_usuario = fp.id_usuario
LEFT JOIN fact_reservas fr ON du.id_usuario = fr.id_usuario
WHERE du.ciudad IS NOT NULL AND du.pais IS NOT NULL
GROUP BY du.ciudad, du.pais
HAVING COUNT(fp.id_pedido) > 0
ORDER BY ingresos_zona DESC;

-- Análisis temporal por zona
CREATE OR REPLACE VIEW v_actividad_zona_temporal AS
SELECT 
    du.ciudad,
    du.pais,
    dt.anio,
    dt.mes,
    dt.nombre_mes,
    COUNT(fp.id_pedido) as pedidos_mes,
    SUM(fp.precio_total) as ingresos_mes,
    COUNT(DISTINCT du.id_usuario) as clientes_activos
FROM dim_usuario du
JOIN fact_pedidos fp ON du.id_usuario = fp.id_usuario
JOIN dim_tiempo dt ON fp.id_tiempo = dt.id_tiempo
WHERE fp.estado = 'completado'
GROUP BY du.ciudad, du.pais, dt.anio, dt.mes, dt.nombre_mes
ORDER BY du.ciudad, dt.anio DESC, dt.mes DESC;

-- Distribución de clientes por zona y edad
CREATE OR REPLACE VIEW v_demografia_zona AS
SELECT 
    du.ciudad,
    du.pais,
    CASE 
        WHEN du.edad < 25 THEN '18-24'
        WHEN du.edad < 35 THEN '25-34'
        WHEN du.edad < 45 THEN '35-44'
        WHEN du.edad < 55 THEN '45-54'
        ELSE '55+'
    END as grupo_edad,
    COUNT(DISTINCT du.id_usuario) as total_clientes,
    AVG(fp.precio_total) as ticket_promedio_grupo
FROM dim_usuario du
LEFT JOIN fact_pedidos fp ON du.id_usuario = fp.id_usuario
WHERE du.ciudad IS NOT NULL AND du.edad IS NOT NULL
GROUP BY du.ciudad, du.pais, 
    CASE 
        WHEN du.edad < 25 THEN '18-24'
        WHEN du.edad < 35 THEN '25-34'
        WHEN du.edad < 45 THEN '35-44'
        WHEN du.edad < 55 THEN '45-54'
        ELSE '55+'
    END
ORDER BY du.ciudad, du.pais, grupo_edad;

-- =====================================================
-- DASHBOARD 3: ESTADÍSTICAS DE PEDIDOS COMPLETADOS VS CANCELADOS
-- =====================================================

-- Consulta principal: Estado de pedidos
CREATE OR REPLACE VIEW v_estadisticas_pedidos AS
SELECT 
    fp.estado,
    COUNT(fp.id_pedido) as total_pedidos,
    SUM(fp.precio_total) as valor_total,
    AVG(fp.precio_total) as valor_promedio,
    ROUND(
        COUNT(fp.id_pedido) * 100.0 / SUM(COUNT(fp.id_pedido)) OVER (), 2
    ) as porcentaje_total
FROM fact_pedidos fp
GROUP BY fp.estado
ORDER BY total_pedidos DESC;

-- Análisis temporal de estados de pedidos
CREATE OR REPLACE VIEW v_pedidos_estado_temporal AS
SELECT 
    dt.anio,
    dt.mes,
    dt.nombre_mes,
    dt.dia_semana,
    dt.nombre_dia_semana,
    fp.estado,
    COUNT(fp.id_pedido) as total_pedidos,
    SUM(fp.precio_total) as valor_total,
    ROUND(
        COUNT(fp.id_pedido) * 100.0 / SUM(COUNT(fp.id_pedido)) OVER (
            PARTITION BY dt.anio, dt.mes
        ), 2
    ) as porcentaje_mes
FROM fact_pedidos fp
JOIN dim_tiempo dt ON fp.id_tiempo = dt.id_tiempo
GROUP BY dt.anio, dt.mes, dt.nombre_mes, dt.dia_semana, dt.nombre_dia_semana, fp.estado
ORDER BY dt.anio DESC, dt.mes DESC, dt.dia_semana, fp.estado;

-- Análisis por restaurante
CREATE OR REPLACE VIEW v_pedidos_por_restaurante AS
SELECT 
    dr.nombre as restaurante,
    dr.ciudad as ciudad_restaurante,
    fp.estado,
    COUNT(fp.id_pedido) as total_pedidos,
    SUM(fp.precio_total) as valor_total,
    ROUND(
        COUNT(fp.id_pedido) * 100.0 / SUM(COUNT(fp.id_pedido)) OVER (
            PARTITION BY dr.id_restaurante
        ), 2
    ) as porcentaje_restaurante,
    AVG(fp.precio_total) as ticket_promedio
FROM fact_pedidos fp
JOIN dim_restaurante dr ON fp.id_restaurante = dr.id_restaurante
GROUP BY dr.nombre, dr.ciudad, fp.estado
ORDER BY dr.nombre, total_pedidos DESC;

-- Análisis de cancelaciones por categoría de producto
CREATE OR REPLACE VIEW v_cancelaciones_categoria AS
SELECT 
    dm.categoria,
    COUNT(CASE WHEN fp.estado = 'completado' THEN 1 END) as pedidos_completados,
    COUNT(CASE WHEN fp.estado = 'cancelado' THEN 1 END) as pedidos_cancelados,
    COUNT(fp.id_pedido) as total_pedidos,
    ROUND(
        COUNT(CASE WHEN fp.estado = 'cancelado' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(fp.id_pedido), 0), 2
    ) as tasa_cancelacion,
    SUM(CASE WHEN fp.estado = 'completado' THEN fp.precio_total ELSE 0 END) as ingresos_completados,
    SUM(CASE WHEN fp.estado = 'cancelado' THEN fp.precio_total ELSE 0 END) as ingresos_perdidos
FROM fact_pedidos fp
JOIN dim_menu dm ON fp.id_menu = dm.id_menu
GROUP BY dm.categoria
ORDER BY tasa_cancelacion DESC;

-- Métricas de rendimiento por hora del día
CREATE OR REPLACE VIEW v_rendimiento_horario AS
SELECT 
    dt.hora,
    COUNT(fp.id_pedido) as total_pedidos,
    COUNT(CASE WHEN fp.estado = 'completado' THEN 1 END) as pedidos_completados,
    COUNT(CASE WHEN fp.estado = 'cancelado' THEN 1 END) as pedidos_cancelados,
    ROUND(
        COUNT(CASE WHEN fp.estado = 'completado' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(fp.id_pedido), 0), 2
    ) as tasa_completado,
    SUM(CASE WHEN fp.estado = 'completado' THEN fp.precio_total ELSE 0 END) as ingresos_hora
FROM fact_pedidos fp
JOIN dim_tiempo dt ON fp.id_tiempo = dt.id_tiempo
GROUP BY dt.hora
ORDER BY dt.hora; 