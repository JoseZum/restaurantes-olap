FROM eclipse-temurin:8-jdk-jammy

# Instalar dependencias necesarias
RUN apt-get update && apt-get install -y \
    curl \
    netcat-openbsd \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Variables de versiones
ENV HIVE_VERSION=3.1.3
ENV HADOOP_VERSION=3.3.4
ENV POSTGRES_JDBC_VERSION=42.5.1

# Directorios base
ENV HIVE_HOME=/opt/hive
ENV HADOOP_HOME=/opt/hadoop
ENV HADOOP_CONF_DIR=/opt/hadoop/conf
ENV PATH=$HIVE_HOME/bin:$HADOOP_HOME/bin:$PATH

# Crear usuario hive
RUN useradd -ms /bin/bash hive

# Instalar Hadoop
RUN curl -L https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz | \
    tar -xz -C /opt/ && \
    mv /opt/hadoop-${HADOOP_VERSION} ${HADOOP_HOME} && \
    mkdir -p ${HADOOP_CONF_DIR}

# Instalar Hive
RUN curl -L https://archive.apache.org/dist/hive/hive-${HIVE_VERSION}/apache-hive-${HIVE_VERSION}-bin.tar.gz | \
    tar -xz -C /opt/ && \
    mv /opt/apache-hive-${HIVE_VERSION}-bin ${HIVE_HOME}

# Descargar el driver JDBC de PostgreSQL
RUN curl -L https://jdbc.postgresql.org/download/postgresql-${POSTGRES_JDBC_VERSION}.jar \
    -o ${HIVE_HOME}/lib/postgresql-${POSTGRES_JDBC_VERSION}.jar

# Crear directorios necesarios
RUN mkdir -p ${HIVE_HOME}/warehouse && \
    mkdir -p ${HIVE_HOME}/tmp && \
    mkdir -p ${HIVE_HOME}/conf && \
    chown -R hive:hive ${HIVE_HOME} && \
    chown -R hive:hive ${HADOOP_HOME}

# Copiar archivos de configuración
COPY conf/hive-site.xml ${HIVE_HOME}/conf/
COPY conf/core-site.xml ${HADOOP_CONF_DIR}/
COPY entrypoint.sh /entrypoint.sh

# Dar permisos de ejecución
RUN chmod +x /entrypoint.sh

# Cambiar al usuario hive
USER hive

# Exponer puertos
EXPOSE 9083 10000 10002


USER root
RUN chown -R 1001:1001 /opt/hive/warehouse
USER hive

# Punto de entrada
ENTRYPOINT ["/entrypoint.sh"]
