# Configuracion del ETL - Configurado para el esquema especifico del proyecto

# Conexion a la base de datos OLTP
OLTP_CONFIG = {
    "host": "postgres-db",  # Base de datos OLTP en docker-compose
    "port": 5432,
    "database": "reserva_db",  # Base de datos del proyecto
    "user": "postgres",
    "password": "1234a"
}

# Mapeo de tablas OLTP a dimensiones DW - Configurado segun el esquema del proyecto
TABLE_MAPPINGS = {
    "usuarios": {
        "source_table": "usuarios",
        "columns": {
            "id": "usuario_id",
            "email": "email",
            "rol": "rol",
            "fecha_alta": "fecha_alta"
        }
    },
    "restaurantes": {
        "source_table": "restaurantes",
        "columns": {
            "id": "restaurante_id",
            "nombre": "nombre",
            "categoria_local": "categoria",
            "capacidad": "capacidad",
            "lat": "lat",
            "lon": "lon"
        }
    },
    "menus": {
        "source_table": "menus",
        "columns": {
            "id": "menu_id",
            "titulo": "titulo_menu",
            "categoria": "categoria_menu",
            "activo": "activo",
            "restaurante_id": "restaurante_id"
        }
    },
    "reservas": {
        "source_table": "reservas",
        "columns": {
            "id": "reserva_id",
            "usuario_id": "usuario_id",
            "restaurante_id": "restaurante_id",
            "fecha": "fecha_reserva",
            "estado": "estado_reserva",
            "invitados": "invitados"
        }
    },
    "pedidos": {
        "source_table": "pedidos",
        "columns": {
            "id": "pedido_id",
            "menu_id": "menu_id",
            "total": "total",
            "estado": "estado_pedido",
            "restaurante_id": "restaurante_id",
            "usuario_id": "usuario_id"
        }
    }
}

# Consultas personalizadas para extracciones complejas
CUSTOM_QUERIES = {
    # Consulta para extraer reservas con informacion completa
    "reservas_completas": """
        SELECT 
            r.id as reserva_id,
            r.usuario_id,
            r.restaurante_id,
            CONCAT(r.fecha, ' ', r.hora)::timestamp as fecha_reserva,
            r.estado as estado_reserva,
            r.invitados,
            COALESCE(p.total, 0) as total,
            COALESCE(p.estado, 'sin_pedido') as estado_pedido,
            r.menu_id
        FROM reservas r
        LEFT JOIN pedidos p ON r.pedido_id = p.id
        WHERE r.fecha >= CURRENT_DATE - INTERVAL '1 year'
    """,
    
    # Consulta para productos activos con informacion del restaurante
    "menus_activos": """
        SELECT 
            m.id,
            m.titulo,
            m.categoria,
            m.activo,
            m.restaurante_id,
            r.nombre as restaurante_nombre
        FROM menus m
        JOIN restaurantes r ON m.restaurante_id = r.id
        WHERE m.activo = true
    """
}

# Configuracion de validaciones de calidad
QUALITY_CHECKS = {
    "min_records": {
        "dim_usuario": 10,
        "dim_restaurante": 5,
        "dim_menu": 20,
        "hechos_reservas": 50
    },
    "required_columns": {
        "hechos_reservas": ["tiempo_id", "usuario_id", "restaurante_id", "total"],
        "dim_tiempo": ["tiempo_id", "fecha", "ano", "mes", "dia"]
    },
    "value_ranges": {
        "total": {"min": 0, "max": 10000},
        "invitados": {"min": 1, "max": 50}
    }
}
