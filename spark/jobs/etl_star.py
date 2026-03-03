from pyspark.sql import SparkSession
import os

spark = (
    SparkSession.builder
    .appName("AppNameAquí")
    # indicamos dónde está el warehouse (mismo volumen de Hive)
    .config("spark.sql.warehouse.dir", os.getenv("SPARK_WAREHOUSE", "hdfs://hdfs-namenode:9000/user/hive/warehouse"))
    .config("spark.hadoop.hive.metastore.uris", "thrift://hive:9083")
    .enableHiveSupport()          # importante para que Spark entienda las tablas Hive
    .getOrCreate()
)

# seleccionamos la base de datos que creamos en init_star.sql
spark.sql("USE restaurantes_dw")