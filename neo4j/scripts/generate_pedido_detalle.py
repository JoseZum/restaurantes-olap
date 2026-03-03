#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de pedido_detalle.csv para análisis de co-compras en Neo4j.

Este script es INDEPENDIENTE del pipeline original y solo genera datos auxiliares
para análisis de grafos en Neo4j. No modifica ningún dato original.

Genera un archivo pedido_detalle.csv donde:
- Cada fila representa un producto incluido en un pedido
- Cada pedido tiene entre 1 y 4 productos del mismo restaurante
- Solo incluye productos válidos (que pertenecen al restaurante del pedido)
- Los pedidos están asignados a usuarios existentes
"""

import os
import random
import pandas as pd
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import logging

# Configuración
SPARK_DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[2] / "spark" / "data"))
NEO4J_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = NEO4J_DATA_DIR / "pedido_detalle.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

def generate_pedido_detalle():
    """
    Genera el archivo pedido_detalle.csv basado en los datos existentes.
    """
    
    # Cargar datos existentes
    log.info("Cargando datos existentes...")
    
    try:
        usuarios_df = pd.read_csv(SPARK_DATA_DIR / "usuarios.csv")
        restaurantes_df = pd.read_csv(SPARK_DATA_DIR / "restaurantes.csv")
        menus_df = pd.read_csv(SPARK_DATA_DIR / "menus.csv")
        pedidos_df = pd.read_csv(SPARK_DATA_DIR / "pedidos.csv")
    except FileNotFoundError as e:
        log.error(f"Error al cargar archivos CSV: {e}")
        return False
    
    log.info(f"Usuarios: {len(usuarios_df)}, Restaurantes: {len(restaurantes_df)}")
    log.info(f"Menús: {len(menus_df)}, Pedidos: {len(pedidos_df)}")
    
    # Filtrar solo productos activos
    productos_activos = menus_df[menus_df['activo'] == 't'].copy()
    log.info(f"Productos activos: {len(productos_activos)}")
    
    # Agrupar productos por restaurante para facilitar la selección
    productos_por_restaurante = productos_activos.groupby('restaurante_id')['id'].apply(list).to_dict()
    
    # Generar detalles de pedido
    log.info("Generando detalles de pedido...")
    
    pedido_detalle_rows = []
    
    for _, pedido in pedidos_df.iterrows():
        pedido_id = pedido['id']
        restaurante_id = pedido['restaurante_id']
        
        # Verificar que el restaurante tenga productos disponibles
        if restaurante_id not in productos_por_restaurante:
            log.warning(f"Restaurante {restaurante_id} no tiene productos activos, saltando pedido {pedido_id}")
            continue
        
        productos_disponibles = productos_por_restaurante[restaurante_id]
        
        # Determinar cuántos productos incluir en este pedido (1-4)
        num_productos = random.randint(1, 4)
        
        # Seleccionar productos únicos para este pedido
        productos_seleccionados = random.sample(
            productos_disponibles, 
            min(num_productos, len(productos_disponibles))
        )
        
        # Generar detalles para cada producto seleccionado
        for producto_id in productos_seleccionados:
            # Cantidad aleatoria entre 1 y 3
            cantidad = random.randint(1, 3)
            
            # Precio unitario aleatorio entre 5.00 y 25.00
            precio_base = random.uniform(5.0, 25.0)
            # Redondear a 2 decimales
            precio_unitario = float(Decimal(str(precio_base)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            
            pedido_detalle_rows.append({
                'pedido_id': pedido_id,
                'producto_id': producto_id,
                'cantidad': cantidad,
                'precio_unitario': precio_unitario
            })
    
    # Crear DataFrame y guardar
    log.info(f"Generando archivo con {len(pedido_detalle_rows)} detalles de pedido...")
    
    pedido_detalle_df = pd.DataFrame(pedido_detalle_rows)
    
    # Guardar archivo
    pedido_detalle_df.to_csv(OUTPUT_FILE, index=False)
    
    log.info(f"Archivo generado exitosamente: {OUTPUT_FILE}")
    log.info(f"Estadisticas:")
    log.info(f"  - Total detalles: {len(pedido_detalle_df)}")
    log.info(f"  - Pedidos únicos: {pedido_detalle_df['pedido_id'].nunique()}")
    log.info(f"  - Productos únicos: {pedido_detalle_df['producto_id'].nunique()}")
    log.info(f"  - Promedio productos por pedido: {len(pedido_detalle_df) / pedido_detalle_df['pedido_id'].nunique():.2f}")
    
    return True

def main():
    """Función principal"""
    log.info("Iniciando generacion de pedido_detalle.csv")
    
    # Verificar que los directorios existen
    if not SPARK_DATA_DIR.exists():
        log.error(f"Directorio de datos de Spark no encontrado: {SPARK_DATA_DIR}")
        return 1
    
    # Crear directorio Neo4j/data si no existe
    NEO4J_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generar archivo
    if generate_pedido_detalle():
        log.info("Proceso completado exitosamente")
        return 0
    else:
        log.error("Error durante la generacion")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main()) 