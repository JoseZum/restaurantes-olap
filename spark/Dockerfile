# ---- Spark sobre Bitnami con Python 3 ----
    FROM bitnami/spark:3.5

    # Pasamos a root para instalar librerías y preparar directorios
    USER root
    
    # Instalamos pandas, pyarrow y numpy, creamos el warehouse y ajustamos permisos
    RUN pip install pandas pyarrow==15.0.2 numpy \
        && mkdir -p /opt/hive/warehouse \
        && chown -R 1001:1001 /opt/hive/warehouse \
        # Damos permisos universales para que otros contenedores (p.e. Airflow
        # que corre como usuario "airflow" UID 50000) puedan escribir sin
        # problemas.  Esto evita errores de "Permission denied" cuando el
        # driver de Spark se lanza desde Airflow en modo *client*.
        && chmod -R 777 /opt/hive/warehouse
    
    # Volvemos a ejecutar como usuario no privilegiado
    USER 1001
    
    # Directorio de trabajo dentro de la imagen
    WORKDIR /opt/bitnami/spark
    
    # Copiamos configuración personalizada de Spark
    COPY conf/spark-env.sh /opt/bitnami/spark/conf/spark-env.sh
    