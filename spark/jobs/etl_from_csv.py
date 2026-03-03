#!/usr/bin/env python3
import os
import logging
import shutil

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    to_timestamp, concat_ws, year, month, dayofmonth,
    hour, date_format, monotonically_increasing_id, col
)
from py4j.java_gateway import java_import

# ——————————————————————————————————————————————————————————————
# Configuración básica de logging
# ——————————————————————————————————————————————————————————————
logging.basicConfig(
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('etl_from_csv')
logger.setLevel(logging.DEBUG)


def drop_table_and_cleanup(spark, table_name, db_name="restaurantes_dw"):
    """
    Elimina la tabla del metastore y borra el directorio asociado si queda huérfano,
    usando la API de Hadoop FS; si todo falla, recurre a shutil.rmtree().
    """
    # 1) Drop metastore entry
    spark.sql(f"DROP TABLE IF EXISTS {db_name}.{table_name} PURGE")
    logger.debug("Dropped table if existed: %s.%s", db_name, table_name)

    # 2) Ruta en warehouse
    warehouse = spark.conf.get("spark.sql.warehouse.dir")
    if warehouse.startswith("file:"):
        warehouse = warehouse[len("file:"):]
    path = f"{warehouse}/{db_name}.db/{table_name}"
    logger.debug("Cleaning directory via Hadoop FS: %s", path)

    # 3) API Hadoop FS
    hadoop_conf = spark._jsc.hadoopConfiguration()
    java_import(spark._jvm, "org.apache.hadoop.fs.Path")
    java_import(spark._jvm, "org.apache.hadoop.fs.FileUtil")
    java_import(spark._jvm, "org.apache.hadoop.fs.permission.FsPermission")

    path_obj = spark._jvm.Path(path)
    fs = spark._jvm.org.apache.hadoop.fs.FileSystem.get(path_obj.toUri(), hadoop_conf)
    perm_777 = spark._jvm.org.apache.hadoop.fs.permission.FsPermission.valueOf("drwxrwxrwx")

    def _chmod_recursive(p):
        try:
            fs.setPermission(p, perm_777)
            if fs.isDirectory(p):
                for status in fs.listStatus(p):
                    _chmod_recursive(status.getPath())
        except Exception as e:
            logger.debug("No se pudo chmod %s: %s", p, e)

    def _delete_fs(p):
        try:
            return fs.delete(p, True)
        except Exception:
            _chmod_recursive(p)
            try:
                return fs.delete(p, True)
            except Exception as e2:
                logger.debug("Retry fs.delete falló %s: %s", p, e2)
                return False

    deleted = _delete_fs(path_obj)
    if not deleted and fs.exists(path_obj):
        logger.warning("fs.delete falló, intentando FileUtil.fullyDelete sobre %s", path)
        try:
            deleted = spark._jvm.org.apache.hadoop.fs.FileUtil.fullyDelete(fs, path_obj)
        except Exception as e:
            logger.error("FileUtil.fullyDelete también falló %s: %s", path, e)
    if not deleted and fs.exists(path_obj):
        logger.warning("Limpiando hijos uno a uno en %s", path)
        try:
            for status in fs.listStatus(path_obj):
                _delete_fs(status.getPath())
        except Exception:
            pass
        deleted = _delete_fs(path_obj)

    # 4) Fallback Python
    if fs.exists(path_obj):
        try:
            logger.warning("Fallback shutil.rmtree %s", path)
            shutil.rmtree(path, ignore_errors=True)
            deleted = True
        except Exception as e:
            logger.error("shutil.rmtree falló %s: %s", path, e)

    if deleted:
        logger.info("Directorio %s eliminado correctamente.", path)
    else:
        logger.warning("No se pudo eliminar %s; continúo.", path)


def ensure_database_dir(spark, warehouse_dir, db_name="restaurantes_dw"):
    """Omitido: asumo que el init-container ya creó y dio permisos al directorio."""
    logger = logging.getLogger(__name__)
    logger.debug("ensure_database_dir omitido: asumo que '%s/%s.db' ya existe y es accesible.",
                 warehouse_dir.rstrip('/'), db_name)


def main():
    # ——————————————————————————————————————————————————————
    # Iniciar Spark con Hive support
    # ——————————————————————————————————————————————————————
    warehouse_dir = os.getenv("SPARK_WAREHOUSE", "hdfs://hdfs-namenode:9000/user/hive/warehouse")

    spark = (
        SparkSession.builder
            .appName("ETLFromCSV")
            .config("spark.sql.warehouse.dir", warehouse_dir)
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
    logger.info("SparkSession arrancada con Hive support")

    # Asegurar que la base de datos exista y apunte al nuevo directorio del
    # warehouse.  Si ya existía con la ubicación antigua (/opt/hive/warehouse)
    # la movemos.

    spark.sql("CREATE DATABASE IF NOT EXISTS restaurantes_dw")
    spark.sql(f"ALTER DATABASE restaurantes_dw SET LOCATION '{warehouse_dir}/restaurantes_dw.db'")
    spark.sql("USE restaurantes_dw")

    # Garantizar que el directorio físico de la base de datos existe y es escribible
    ensure_database_dir(spark, warehouse_dir)

    # Opcional: intentar limpiar la antigua ubicación para evitar colisiones
    old_db_path = "/opt/hive/warehouse/restaurantes_dw.db"
    if old_db_path != f"{warehouse_dir}/restaurantes_dw.db" and os.path.exists(old_db_path):
        try:
            shutil.rmtree(old_db_path, ignore_errors=True)
            logger.info("Antiguo directorio de la base de datos eliminado: %s", old_db_path)
        except Exception as e:
            logger.warning("No se pudo eliminar el antiguo directorio %s: %s", old_db_path, e)

    # Carga de CSVs
    # Prefijamos con file:// para que Spark lea desde el sistema de archivos
    # local del contenedor (y no desde HDFS) independientemente de fs.defaultFS.
    usuarios     = spark.read.option("header", True).csv("file:///opt/spark/data/usuarios.csv")
    restaurantes = spark.read.option("header", True).csv("file:///opt/spark/data/restaurantes.csv")
    menus        = spark.read.option("header", True).csv("file:///opt/spark/data/menus.csv")
    reservas     = spark.read.option("header", True).csv("file:///opt/spark/data/reservas.csv")
    pedidos      = spark.read.option("header", True).csv("file:///opt/spark/data/pedidos.csv")
    logger.info("CSV cargados en DataFrames")

    # DIMENSIONES
    dims = [
        ("dim_usuario", usuarios, [
            "id AS usuario_id", "email", "rol", "fecha_alta"
        ]),
        ("dim_restaurante", restaurantes, [
            "id AS restaurante_id", "nombre",
            "categoria_local AS categoria", "capacidad", "lat", "lon"
        ]),
        ("dim_menu", menus, [
            "id AS menu_id", "titulo AS titulo_menu",
            "categoria AS categoria_menu", "activo", "restaurante_id"
        ]),
    ]
    for name, df, exprs in dims:
        drop_table_and_cleanup(spark, name)
        df.selectExpr(*exprs).write.mode("overwrite").saveAsTable(name)
        logger.info("Tabla %s reconstruida", name)

    # HECHOS: unir reservas + pedidos
    reservas = reservas.withColumn(
        "timestamp_reserva",
        to_timestamp(concat_ws(" ", reservas.fecha, reservas.hora))
    )
    pedidos = pedidos.withColumnRenamed("id", "pedido_id")

    # Alias para evitar ambigüedades en columnas duplicadas (p.e. usuario_id)
    r = reservas.alias("r")
    p = pedidos.alias("p")

    hechos = r.join(p, "pedido_id", "left") \
        .select(
            col("r.usuario_id").alias("usuario_id"),
            col("r.restaurante_id").alias("restaurante_id"),
            col("r.menu_id").alias("menu_id"),
            col("r.timestamp_reserva").alias("fecha_reserva"),
            col("r.estado").alias("estado_reserva"),
            col("p.total"),
            col("p.estado").alias("estado_pedido"),
            col("r.invitados")
        )
    logger.info("DataFrame de hechos preparado")

    # DIM_TIEMPO
    drop_table_and_cleanup(spark, "dim_tiempo")
    tiempo = hechos.select("fecha_reserva").distinct() \
        .withColumn("tiempo_id", monotonically_increasing_id()) \
        .withColumn("ano", year("fecha_reserva")) \
        .withColumn("mes", month("fecha_reserva")) \
        .withColumn("dia", dayofmonth("fecha_reserva")) \
        .withColumn("hora", hour("fecha_reserva")) \
        .withColumn("nombre_mes_completo", date_format("fecha_reserva", "MMMM")) \
        .withColumn("dia_semana", date_format("fecha_reserva", "EEEE"))
    tiempo.write.mode("overwrite").saveAsTable("dim_tiempo")
    logger.info("Tabla dim_tiempo reconstruida")

    # FACT TABLE
    hechos_final = hechos.join(tiempo, "fecha_reserva") \
        .select("tiempo_id", "usuario_id", "restaurante_id",
                "menu_id", "total", "estado_reserva",
                "estado_pedido", "invitados")
    drop_table_and_cleanup(spark, "hechos_reservas")
    hechos_final.write.mode("overwrite").saveAsTable("hechos_reservas")
    logger.info("Tabla hechos_reservas reconstruida")

    spark.stop()
    logger.info("ETL completado y Spark detenido.")


# ---------------------------------------------------------------------------
# Punto de entrada con captura total de excepciones para mejorar depuración
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Fallo crítico en ETL: %s", e)
        raise
