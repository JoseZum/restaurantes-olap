from pyspark.sql import SparkSession
from pyspark.sql.functions import *
import time
import os

def clean_hdfs_directory(spark, table_name):
    """Elimina el directorio HDFS de una tabla si existe"""
    try:
        hadoop_conf = spark._jsc.hadoopConfiguration()
        fs = spark._jvm.org.apache.hadoop.fs.FileSystem.get(hadoop_conf)
        hdfs_path = spark._jvm.org.apache.hadoop.fs.Path(f"/user/hive/warehouse/restaurantes_dw.db/{table_name}")
        if fs.exists(hdfs_path):
            fs.delete(hdfs_path, True)  # True para eliminación recursiva
            print(f"Directorio HDFS eliminado: {table_name}")
            return True
        else:
            print(f"Directorio HDFS no existe: {table_name}")
            return False
    except Exception as e:
        print(f"Advertencia: No se pudo eliminar directorio HDFS {table_name}: {e}")
        return False

def wait_for_hive(spark, max_attempts=30):
    """Espera a que Hive esté disponible"""
    for i in range(max_attempts):
        try:
            spark.sql("SHOW DATABASES").collect()
            print("Conexion con Hive establecida")
            return True
        except Exception as e:
            print(f"Esperando a Hive... intento {i+1}/{max_attempts}")
            time.sleep(2)
    return False

def main():
    print("=== Iniciando análisis de tendencias de consumo ===")
    
    # Crear sesión de Spark con configuración completa
    spark = (
        SparkSession.builder
        .appName("TendenciasConsumo")
        .config("spark.sql.warehouse.dir", os.getenv("SPARK_WAREHOUSE", "hdfs://hdfs-namenode:9000/user/hive/warehouse"))
        .config("spark.hadoop.hive.metastore.uris", "thrift://hive:9083")
        .config("spark.sql.catalogImplementation", "hive")
        .config("spark.sql.hive.metastore.version", "3.1.3")
        .config("spark.sql.hive.metastore.jars", "maven")
        .config("spark.jars.ivy", "/tmp/.ivy2")
        .config("spark.driver.extraJavaOptions", "-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2")
        .config("spark.executor.extraJavaOptions", "-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2")
        .config("spark.hadoop.fs.defaultFS", "hdfs://hdfs-namenode:9000")
        .config("spark.jars", "/opt/drivers/postgresql-42.5.1.jar")
        .enableHiveSupport()
        .getOrCreate()
    )
    
    # Configurar nivel de log
    spark.sparkContext.setLogLevel("WARN")
    
    # Esperar a que Hive esté disponible
    if not wait_for_hive(spark):
        print("ERROR: No se pudo conectar con Hive")
        spark.stop()
        return
    
    try:
        # Mostrar bases de datos disponibles
        print("\n=== Bases de datos disponibles ===")
        spark.sql("SHOW DATABASES").show()
        
        # Usar la base de datos del data warehouse
        spark.sql("USE restaurantes_dw")
        
        # Mostrar tablas disponibles
        print("\n=== Tablas en restaurantes_dw ===")
        spark.sql("SHOW TABLES").show()
        
        # Verificar si hay datos en las tablas
        print("\n=== Verificando datos ===")
        count_hechos = spark.sql("SELECT COUNT(*) as total FROM hechos_reservas").collect()[0]['total']
        print(f"Total de registros en hechos_reservas: {count_hechos}")
        
        if count_hechos == 0:
            print("ADVERTENCIA: No hay datos en la tabla de hechos")
            print("Debes cargar datos primero usando el ETL")
        else:
            # Análisis 1: Tendencias de consumo por mes y categoría
            print("\n=== Análisis 1: Tendencias de consumo ===")
            df_tendencias = spark.sql("""
                SELECT
                    t.ano,
                    t.mes,
                    t.nombre_mes_completo,
                    m.categoria_menu,
                    COUNT(*) as num_pedidos,
                    SUM(h.total) AS ingresos_total,
                    AVG(h.total) AS ticket_promedio
                FROM hechos_reservas h
                JOIN dim_tiempo t ON h.tiempo_id = t.tiempo_id
                JOIN dim_menu m ON h.menu_id = m.menu_id
                WHERE h.total > 0
                GROUP BY t.ano, t.mes, t.nombre_mes_completo, m.categoria_menu
                ORDER BY t.ano, t.mes, m.categoria_menu
            """)
            
            print("Primeras 20 filas:")
            df_tendencias.show(20, truncate=False)
            
            # Guardar como tabla para dashboards
            print("Eliminando tabla dw_tendencias_consumo si existe...")
            spark.sql("DROP TABLE IF EXISTS restaurantes_dw.dw_tendencias_consumo")
            clean_hdfs_directory(spark, "dw_tendencias_consumo")
            df_tendencias.write.mode("overwrite").saveAsTable("dw_tendencias_consumo")
            print("Tabla 'dw_tendencias_consumo' creada/actualizada")
            
            # Análisis 2: Horarios pico
            print("\n=== Análisis 2: Horarios pico ===")
            df_horarios = spark.sql("""
                SELECT
                    t.hora,
                    t.dia_semana,
                    COUNT(*) as num_reservas,
                    SUM(h.total) as ingresos_hora,
                    AVG(h.invitados) as promedio_invitados
                FROM hechos_reservas h
                JOIN dim_tiempo t ON h.tiempo_id = t.tiempo_id
                WHERE h.estado_reserva = 'ACTIVE'
                GROUP BY t.hora, t.dia_semana
                ORDER BY t.hora
            """)
            
            print("Distribución por hora del día:")
            df_horarios.show(24, truncate=False)
            
            # Guardar como tabla
            print("Eliminando tabla dw_horarios_pico si existe...")
            spark.sql("DROP TABLE IF EXISTS restaurantes_dw.dw_horarios_pico")
            clean_hdfs_directory(spark, "dw_horarios_pico")
            df_horarios.write.mode("overwrite").saveAsTable("dw_horarios_pico")
            print("Tabla 'dw_horarios_pico' creada/actualizada")
            
            # Análisis 3: Crecimiento mensual
            print("\n=== Análisis 3: Crecimiento mensual ===")
            df_crecimiento = spark.sql("""
                WITH ingresos_mensuales AS (
                    SELECT
                        t.ano,
                        t.mes,
                        SUM(h.total) as ingresos_mes,
                        COUNT(DISTINCT h.usuario_id) as usuarios_activos,
                        COUNT(*) as total_reservas
                    FROM hechos_reservas h
                    JOIN dim_tiempo t ON h.tiempo_id = t.tiempo_id
                    GROUP BY t.ano, t.mes
                )
                SELECT
                    ano,
                    mes,
                    ingresos_mes,
                    usuarios_activos,
                    total_reservas,
                    ingresos_mes - LAG(ingresos_mes, 1) OVER (ORDER BY ano, mes) as cambio_ingresos,
                    ROUND(
                        100.0 * (ingresos_mes - LAG(ingresos_mes, 1) OVER (ORDER BY ano, mes)) / 
                        NULLIF(LAG(ingresos_mes, 1) OVER (ORDER BY ano, mes), 0), 
                        2
                    ) as porcentaje_crecimiento
                FROM ingresos_mensuales
                ORDER BY ano, mes
            """)
            
            print("Crecimiento mes a mes:")
            df_crecimiento.show(truncate=False)
            
            # Guardar como tabla
            print("Eliminando tabla dw_crecimiento_mensual si existe...")
            spark.sql("DROP TABLE IF EXISTS restaurantes_dw.dw_crecimiento_mensual")
            clean_hdfs_directory(spark, "dw_crecimiento_mensual")
            df_crecimiento.write.mode("overwrite").saveAsTable("dw_crecimiento_mensual")
            print("Tabla 'dw_crecimiento_mensual' creada/actualizada")
            
            # Resumen final
            print("\n=== RESUMEN ===")
            print("Analisis completado exitosamente")
            print("Tablas creadas:")
            print("  - dw_tendencias_consumo")
            print("  - dw_horarios_pico")
            print("  - dw_crecimiento_mensual")
            print("\nEstas tablas están listas para ser usadas en dashboards")
        
    except Exception as e:
        print(f"ERROR durante el análisis: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Cerrar la sesión
        spark.stop()
        print("\n=== Proceso finalizado ===")

if __name__ == "__main__":
    main()
