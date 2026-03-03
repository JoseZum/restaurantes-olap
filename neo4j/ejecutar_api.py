#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para ejecutar el API de rutas directamente
"""

import os
import sys
import subprocess
import time

def check_dependencies():
    """Verificar que las dependencias estén instaladas"""
    try:
        import fastapi
        import uvicorn
        import neo4j
        print("Dependencias encontradas")
        return True
    except ImportError as e:
        print(f"Falta dependencia: {e}")
        print("Instalando dependencias...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "rutas_api/requirements.txt"])
            print("Dependencias instaladas")
            return True
        except subprocess.CalledProcessError:
            print("Error instalando dependencias")
            return False

def check_neo4j_connection():
    """Verificar conexión a Neo4j"""
    try:
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "restaurantes123")
        
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        print("Conexion a Neo4j exitosa")
        return True
    except Exception as e:
        print(f"Advertencia: No se pudo conectar a Neo4j: {e}")
        print("El API funcionará en modo de desarrollo con datos de ejemplo")
        return False

def run_api():
    """Ejecutar el API"""
    print("Iniciando API de Rutas Optimas...")
    
    # Cambiar al directorio del API
    api_dir = os.path.join(os.path.dirname(__file__), "rutas_api")
    os.chdir(api_dir)
    
    # Ejecutar uvicorn
    try:
        import uvicorn
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nAPI detenido por el usuario")
    except Exception as e:
        print(f"Error ejecutando API: {e}")

if __name__ == "__main__":
    print("INICIADOR DEL API DE RUTAS OPTIMAS")
    print("=" * 45)
    
    # Verificar dependencias
    if not check_dependencies():
        sys.exit(1)
    
    # Verificar Neo4j
    check_neo4j_connection()
    
    # Ejecutar API
    run_api() 