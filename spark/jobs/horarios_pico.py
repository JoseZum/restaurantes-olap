from pyspark.sql import SparkSession
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

def main():
    spark = (
        SparkSession.builder
        .appName("HorariosPico")
        .config("spark.sql.warehouse.dir", os.getenv("SPARK_WAREHOUSE", "hdfs://hdfs-namenode:9000/user/hive/warehouse"))
        .config("spark.hadoop.hive.metastore.uris", "thrift://hive:9083")
        .config("spark.sql.catalogImplementation", "hive")
        .config("spark.sql.hive.metastore.version", "3.1.3")
        .config("spark.sql.hive.metastore.jars", "maven")
        .config("spark.jars.ivy", "/tmp/.ivy2")
        .config("spark.driver.extraJavaOptions", "-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2")
        .config("spark.executor.extraJavaOptions", "-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2")
        .config("spark.hadoop.fs.defaultFS", "hdfs://hdfs-namenode:9000")
        .enableHiveSupport()
        .getOrCreate()
    )
    
    try:
        spark.sql("USE restaurantes_dw")

        # Consulta: cuentas reservas por hora
        print("Analizando horarios pico de reservas...")
        df_horas = spark.sql("""
            SELECT
                t.hora,
                COUNT(*) AS total_reservas
            FROM hechos_reservas h
            JOIN dim_tiempo t ON h.tiempo_id = t.tiempo_id
            GROUP BY t.hora
            ORDER BY total_reservas DESC
        """)

        # Mostramos top 10 horas con más reservas
        print("Top 10 horas con más reservas:")
        df_horas.show(10)

        # Guardamos en Hive
        print("Eliminando tabla existente si existe...")
        spark.sql("DROP TABLE IF EXISTS restaurantes_dw.dw_horarios_pico")
        clean_hdfs_directory(spark, "dw_horarios_pico")
        
        print("Guardando resultados en tabla dw_horarios_pico...")
        df_horas.write.mode("overwrite").saveAsTable("dw_horarios_pico")
        
        print("Análisis de horarios pico completado exitosamente")
        
    except Exception as e:
        print(f"Error en el análisis de horarios pico: {str(e)}")
        raise e
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
