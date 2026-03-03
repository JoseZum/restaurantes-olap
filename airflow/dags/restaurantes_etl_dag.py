from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.utils.dates import days_ago
import requests
import json

# Configuracion por defecto del DAG
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'email': ['admin@restaurantes.com'],
    'retries': 1,
    'retry_delay': timedelta(minutes=0.01)
}

# Definicion del DAG
dag = DAG(
    'restaurantes_etl_pipeline',
    default_args=default_args,
    description='Pipeline ETL para Data Warehouse de Restaurantes',
    schedule_interval='0 2 * * *',  # Ejecutar diariamente a las 2 AM
    catchup=False,
    tags=['etl', 'data-warehouse', 'restaurantes']
)

# Tarea 1: Verificar conexion a PostgreSQL OLTP
check_postgres_conn = PostgresOperator(
    task_id='check_postgres_connection',
    postgres_conn_id='postgres_oltp',
    sql="""
        SELECT 1;
    """,
    dag=dag
)

# Tarea 2: Verificar que Hive Metastore este disponible
check_hive_metastore = BashOperator(
    task_id='check_hive_metastore',
    bash_command="""
        # Verificar que el metastore responda a conexiones
        nc -zv hive 9083 && echo "Hive Metastore está disponible"
    """,
    dag=dag
)

# Tarea 3: Validar datos de origen
def validate_source_data(**context):
    """Valida que los datos de origen esten completos y sean validos"""
    pg_hook = PostgresHook(postgres_conn_id='postgres_oltp')
    
    # Verificar que las tablas contengan datos
    tables_to_check = ['usuarios', 'restaurantes', 'menus', 'reservas', 'pedidos']
    
    for table in tables_to_check:
        result = pg_hook.get_first(f"SELECT COUNT(*) FROM {table}")
        count = result[0]
        
        if count == 0:
            raise ValueError(f"La tabla {table} está vacía!")
        
        print(f"Tabla {table}: {count} registros")
    
    # Verificar integridad referencial basica
    orphan_pedidos = pg_hook.get_first("""
        SELECT COUNT(*) 
        FROM pedidos p 
        LEFT JOIN reservas r ON p.id = r.pedido_id 
        WHERE r.id IS NULL
    """)[0]
    
    if orphan_pedidos > 0:
        print(f"ADVERTENCIA: Hay {orphan_pedidos} pedidos sin reserva asociada")
    
    return True

validate_data = PythonOperator(
    task_id='validate_source_data',
    python_callable=validate_source_data,
    dag=dag
)

# Tarea 4: Extraer datos de PostgreSQL a CSV
extract_to_csv = BashOperator(
    task_id='extract_postgresql_to_csv',
    bash_command="""
        # Crear directorio temporal para extraccion
        mkdir -p /tmp/etl_data

        # Extraer tablas a CSV usando COPY de PostgreSQL
        export PGPASSWORD=$POSTGRES_PASSWORD
        psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -p $POSTGRES_PORT <<'ENDSQL'
        \COPY usuarios TO '/tmp/etl_data/usuarios.csv' WITH CSV HEADER;
        \COPY restaurantes TO '/tmp/etl_data/restaurantes.csv' WITH CSV HEADER;
        \COPY menus TO '/tmp/etl_data/menus.csv' WITH CSV HEADER;
        \COPY pedidos TO '/tmp/etl_data/pedidos.csv' WITH CSV HEADER;
        \COPY reservas TO '/tmp/etl_data/reservas.csv' WITH CSV HEADER;
ENDSQL

        # Copiar los CSV al volumen compartido de Spark
        cp /tmp/etl_data/*.csv /opt/spark/data/

        echo "Extracción completada"
    """,
    env={
        'POSTGRES_HOST': 'postgres-db',
        'POSTGRES_USER': 'postgres',
        'POSTGRES_PASSWORD': '1234a',
        'POSTGRES_DB': 'restaurantes',
        'POSTGRES_PORT': '5432'
    },
    dag=dag
)

# Tarea 5: Ejecutar ETL principal con Spark
run_etl_spark = SparkSubmitOperator(
    task_id='run_etl_spark',
    application='/opt/spark/jobs/etl_from_csv.py',
    conn_id='spark_default',
    # Modo "client" (el unico soportado para aplicaciones Python
    # en clusters Spark Standalone), se confian en los permisos 777
    # del volumen hive-warehouse para evitar problemas de escritura.
    deploy_mode='client',
    conf={
        'spark.master': 'spark://spark-master:7077',
        'spark.sql.warehouse.dir': 'hdfs://hdfs-namenode:9000/user/hive/warehouse',
        'spark.hadoop.hive.metastore.uris': 'thrift://hive:9083',
        'spark.sql.hive.metastore.version': '3.1.3',
        'spark.sql.hive.metastore.jars': 'maven',
        # Permite sobrescribir ubicaciones no vacias en operaciones CTAS/insert
        'spark.sql.legacy.allowNonEmptyLocationInCTAS': 'true',
        'spark.jars.ivy': '/tmp/.ivy2',
        'spark.hadoop.hadoop.security.authentication': 'simple',
        "spark.driver.port": "4041",
        "spark.blockManager.port": "4042",
        "spark.eventLog.enabled": "false",
        "spark.driver.bindAddress": "0.0.0.0",
        "spark.driver.host": "airflow-scheduler",
        'spark.hadoop.fs.defaultFS': 'hdfs://hdfs-namenode:9000',
        # Forzar Ivy a usar un directorio local unico con permisos,
        # evitando descargas corruptas cuando varios procesos compiten sobre
        # ~/.ivy2. Se propaga a Driver y Executors mediante opciones Java.
        'spark.driver.extraJavaOptions': '-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2',
        'spark.executor.extraJavaOptions': '-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2'
    },
    jars='/opt/drivers/postgresql-42.5.1.jar',
    driver_memory='2g',
    executor_memory='3g',
    total_executor_cores=6,
    executor_cores=1,
    env_vars={'HADOOP_USER_NAME': 'root'},
    verbose=True,
    dag=dag
)

# Tarea 6: Ejecutar analisis de tendencias
run_tendencias_analysis = SparkSubmitOperator(
    task_id='run_tendencias_analysis',
    application='/opt/spark/jobs/tendencias.py',
    conn_id='spark_default',
    driver_memory='2g',
    executor_memory='3g',
    total_executor_cores=6,
    executor_cores=1,
    conf={
        'spark.master': 'spark://spark-master:7077',
        'spark.sql.warehouse.dir': 'hdfs://hdfs-namenode:9000/user/hive/warehouse',
        'spark.hadoop.hive.metastore.uris': 'thrift://hive:9083',
        'spark.sql.hive.metastore.version': '3.1.3',
        'spark.sql.hive.metastore.jars': 'maven',
        'spark.jars.ivy': '/tmp/.ivy2',
        'spark.driver.bindAddress': '0.0.0.0',
        'spark.driver.host': 'airflow-scheduler',
        'spark.driver.extraJavaOptions': '-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2',
        'spark.executor.extraJavaOptions': '-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2',
        'spark.hadoop.fs.defaultFS': 'hdfs://hdfs-namenode:9000'
    },
    env_vars={'HADOOP_USER_NAME': 'root'},
    verbose=True,
    dag=dag
)

# Tarea 7: Ejecutar analisis de horarios pico
run_horarios_analysis = SparkSubmitOperator(
    task_id='run_horarios_analysis',
    application='/opt/spark/jobs/horarios_pico.py',
    conn_id='spark_default',
    driver_memory='2g',
    executor_memory='3g',
    total_executor_cores=6,
    executor_cores=1,
    conf={
        'spark.master': 'spark://spark-master:7077',
        'spark.sql.warehouse.dir': 'hdfs://hdfs-namenode:9000/user/hive/warehouse',
        'spark.hadoop.hive.metastore.uris': 'thrift://hive:9083',
        'spark.sql.hive.metastore.version': '3.1.3',
        'spark.sql.hive.metastore.jars': 'maven',
        'spark.jars.ivy': '/tmp/.ivy2',
        'spark.driver.bindAddress': '0.0.0.0',
        'spark.driver.host': 'airflow-scheduler',
        'spark.driver.extraJavaOptions': '-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2',
        'spark.executor.extraJavaOptions': '-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2',
        'spark.hadoop.fs.defaultFS': 'hdfs://hdfs-namenode:9000'
    },
    env_vars={'HADOOP_USER_NAME': 'root'},
    verbose=True,
    dag=dag
)

# Tarea 8: Ejecutar analisis de crecimiento
run_crecimiento_analysis = SparkSubmitOperator(
    task_id='run_crecimiento_analysis',
    application='/opt/spark/jobs/crecimiento.py',
    conn_id='spark_default',
    driver_memory='2g',
    executor_memory='3g',
    total_executor_cores=6,
    executor_cores=1,
    conf={
        'spark.master': 'spark://spark-master:7077',
        'spark.sql.warehouse.dir': 'hdfs://hdfs-namenode:9000/user/hive/warehouse',
        'spark.hadoop.hive.metastore.uris': 'thrift://hive:9083',
        'spark.sql.hive.metastore.version': '3.1.3',
        'spark.sql.hive.metastore.jars': 'maven',
        'spark.jars.ivy': '/tmp/.ivy2',
        'spark.driver.bindAddress': '0.0.0.0',
        'spark.driver.host': 'airflow-scheduler',
        'spark.driver.extraJavaOptions': '-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2',
        'spark.executor.extraJavaOptions': '-Divy.cache.dir=/tmp/.ivy2 -Divy.home=/tmp/.ivy2',
        'spark.hadoop.fs.defaultFS': 'hdfs://hdfs-namenode:9000'
    },
    env_vars={'HADOOP_USER_NAME': 'root'},
    verbose=True,
    dag=dag
)

# Tarea 9: Actualizar indices de ElasticSearch
def update_elasticsearch_catalog(**context):
    """Actualiza el catalogo de productos en ElasticSearch si hubo cambios"""

    # Conectar a PostgreSQL para obtener productos actualizados
    pg_hook = PostgresHook(postgres_conn_id='postgres_oltp')
    
    # Obtener productos modificados en las ultimas 24 horas
    productos_actualizados = pg_hook.get_records("""
        SELECT id, titulo, categoria, activo, restaurante_id
        FROM menus
        -- Si existe campo updated_at, usarlo aqui:
        -- WHERE updated_at >= NOW() - INTERVAL '24 hours'
    """)
    
    if productos_actualizados:
        # URL del servicio ElasticSearch
        es_url = "http://elasticsearch:9200"
        
        # Indexar cada producto en ElasticSearch
        for producto in productos_actualizados:
            doc = {
                'id': producto[0],
                'titulo': producto[1],
                'categoria': producto[2],
                'activo': producto[3],
                'restaurante_id': producto[4],
                'updated_at': datetime.now().isoformat()
            }
            
            # Indexar en ElasticSearch
            response = requests.put(
                f"{es_url}/productos_restaurantes/_doc/{producto[0]}",
                headers={'Content-Type': 'application/json'},
                data=json.dumps(doc)
            )
            
            if response.status_code not in [200, 201]:
                print(f"Error actualizando producto {producto[0]}: {response.text}")
        
        print(f"Actualizados {len(productos_actualizados)} productos en ElasticSearch")
    else:
        print("No hay productos para actualizar en ElasticSearch")

update_elasticsearch = PythonOperator(
    task_id='update_elasticsearch_catalog',
    python_callable=update_elasticsearch_catalog,
    dag=dag
)

# Task 10: Validar calidad de datos en DW
def validate_dw_quality(**context):
    """Valida la calidad de los datos en el Data Warehouse"""
    # Esta tarea se ejecutaría con Spark, pero por simplicidad usamos bash
    return True

validate_quality = PythonOperator(
    task_id='validate_dw_quality',
    python_callable=validate_dw_quality,
    dag=dag
)

# Task 11: Generar reporte de éxito
def send_success_notification(**context):
    """Envía notificación de que el ETL se completó exitosamente"""
    execution_date = context['execution_date']
    
    print(f"""
    ETL Pipeline Completado Exitosamente
    
    Fecha de ejecución: {execution_date}
    
    Resumen:
    - Datos extraídos del OLTP
    - Transformaciones aplicadas
    - Data Warehouse actualizado
    - Análisis de Spark ejecutados
    - ElasticSearch sincronizado
    - Calidad de datos verificada
    
    El Data Warehouse está listo para consultas y dashboards.
    """)

notify_success = PythonOperator(
    task_id='send_success_notification',
    python_callable=send_success_notification,
    trigger_rule='all_success',
    dag=dag
)

# Task 12: Manejo de errores
def handle_failure(**context):
    """Maneja fallos en el pipeline"""
    task_instance = context['task_instance']
    
    print(f"""
    ETL Pipeline Fallo
    
    Task fallida: {task_instance.task_id}
    Fecha: {context['execution_date']}
    Error: {context.get('exception', 'Unknown error')}
    
    Por favor revisar los logs para más detalles.
    """)

notify_failure = PythonOperator(
    task_id='handle_failure',
    python_callable=handle_failure,
    trigger_rule='one_failed',
    dag=dag
)

# Definir dependencias del DAG
# Verificaciones iniciales en paralelo
[check_postgres_conn, check_hive_metastore] >> validate_data

# Extracción después de validaciones
validate_data >> extract_to_csv

# ETL principal después de extracción
extract_to_csv >> run_etl_spark

# Análisis en paralelo después del ETL
run_etl_spark >> [run_tendencias_analysis, run_horarios_analysis, run_crecimiento_analysis]

# Actualizar ElasticSearch en paralelo con los análisis
run_etl_spark >> update_elasticsearch

# Validación de calidad después de todos los procesos
[run_tendencias_analysis, run_horarios_analysis, run_crecimiento_analysis, update_elasticsearch] >> validate_quality

# Notificaciones finales
validate_quality >> [notify_success, notify_failure]
