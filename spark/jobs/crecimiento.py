from pyspark.sql import SparkSession
from pyspark.sql.window import Window
import pyspark.sql.functions as F
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
        .appName("CrecimientoMensual")
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

        # Paso 1: obtenemos ingresos totales por año/mes
        df_ingresos = spark.sql("""
            SELECT
                t.ano,
                t.mes,
                SUM(h.total) AS ingresos_mes
            FROM hechos_reservas h
            JOIN dim_tiempo t ON h.tiempo_id = t.tiempo_id
            GROUP BY t.ano, t.mes
            ORDER BY t.ano, t.mes
        """)

        # Paso 2: definimos una ventana de orden por año y mes para calcular lag (mes anterior)
        window_spec = Window.orderBy("ano", "mes")

        # Paso 3: agregamos columna con ingresos del mes anterior
        df_crecimiento = df_ingresos.withColumn(
            "ingresos_prev", F.lag("ingresos_mes", 1).over(window_spec)
        ).withColumn(
            "porcentaje_crecimiento",
            F.when(
                F.col("ingresos_prev").isNotNull(),
                (F.col("ingresos_mes") - F.col("ingresos_prev")) / F.col("ingresos_prev") * 100
            ).otherwise(F.lit(0))
        )

        # Verificamos
        print("Mostrando análisis de crecimiento mensual:")
        df_crecimiento.show(10)

        # Guardamos en Hive
        print("Eliminando tabla existente si existe...")
        spark.sql("DROP TABLE IF EXISTS restaurantes_dw.dw_crecimiento_mensual")
        clean_hdfs_directory(spark, "dw_crecimiento_mensual")
        
        print("Guardando resultados en tabla dw_crecimiento_mensual...")
        df_crecimiento.write.mode("overwrite").saveAsTable("dw_crecimiento_mensual")
        
        print("Análisis de crecimiento completado exitosamente")
        
    except Exception as e:
        print(f"Error en el análisis de crecimiento: {str(e)}")
        raise e
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
