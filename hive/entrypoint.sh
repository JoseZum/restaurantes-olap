#!/bin/bash
set -e

# Esperar a que PostgreSQL esté listo
echo "Esperando a que PostgreSQL esté listo..."
while ! pg_isready -h ${DATABASE_HOST} -p ${DATABASE_PORT} -U ${DATABASE_USER}; do
    echo "PostgreSQL no está listo - esperando..."
    sleep 2
done
echo "PostgreSQL está listo!"

# Inicializar el esquema del metastore si es necesario
echo "Verificando/Inicializando esquema del metastore..."
${HIVE_HOME}/bin/schematool -dbType postgres -validate || {
    echo "Esquema no encontrado, inicializando..."
    ${HIVE_HOME}/bin/schematool -dbType postgres -initSchema
}

# Iniciar el servicio del metastore
echo "Iniciando Hive Metastore..."
${HIVE_HOME}/bin/hive --service metastore &
METASTORE_PID=$!

# Esperar a que el metastore esté listo
echo "Esperando a que el metastore esté listo..."
sleep 10

# Verificar que el metastore esté funcionando
while ! nc -z localhost 9083; do
    echo "Metastore no está listo - esperando..."
    sleep 2
done
echo "Metastore está listo!"

# Ejecutar el script de inicialización si existe
if [ -f "/opt/hive/init_star.sql" ]; then
    echo "Ejecutando script de inicialización..."
    ${HIVE_HOME}/bin/beeline -u jdbc:hive2://localhost:10000 -f /opt/hive/init_star.sql || {
        echo "Primera ejecución del script falló, reintentando después de iniciar HiveServer2..."
    }
fi

# Iniciar HiveServer2
echo "Iniciando HiveServer2..."
${HIVE_HOME}/bin/hive --service hiveserver2 &
HIVESERVER2_PID=$!

# Si el script de inicialización no se ejecutó antes, intentar ahora
if [ -f "/opt/hive/init_star.sql" ]; then
    echo "Esperando a que HiveServer2 esté listo..."
    sleep 15
    while ! nc -z localhost 10000; do
        echo "HiveServer2 no está listo - esperando..."
        sleep 2
    done
    echo "Ejecutando script de inicialización..."
    ${HIVE_HOME}/bin/beeline -u jdbc:hive2://localhost:10000 -f /opt/hive/init_star.sql || echo "Script ya ejecutado o error no crítico"
fi

# Mantener el contenedor en ejecución
echo "Hive está listo y funcionando!"
wait $METASTORE_PID $HIVESERVER2_PID
