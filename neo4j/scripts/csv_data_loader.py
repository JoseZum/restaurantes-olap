#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cargador de Datos CSV para Sistema de Rutas de Entrega
======================================================

Este módulo carga datos reales desde los archivos CSV:
- usuarios.csv -> Clientes del sistema
- restaurantes.csv -> Restaurantes con ubicaciones reales
- pedidos.csv -> Pedidos históricos para simulación
- Genera repartidores aleatorios con ubicaciones OSM

Funcionalidades:
1. Carga usuarios CSV y asigna coordenadas basadas en OSM
2. Carga restaurantes con sus coordenadas reales
3. Carga pedidos históricos y los relaciona con usuarios/restaurantes
4. Genera repartidores aleatorios en ubicaciones OSM válidas
5. Inicializa el sistema completo con datos reales
"""

import csv
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from neo4j import GraphDatabase
import os
import sys

# Agregar el directorio actual al path para importar delivery_routes_system
sys.path.append(os.path.dirname(__file__))
from delivery_routes_system import DeliveryRoutesSystem, Cliente, Repartidor, Pedido

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

class CSVDataLoader:
    """Cargador de datos CSV para el sistema de rutas"""
    
    def __init__(self, delivery_system: DeliveryRoutesSystem):
        self.delivery_system = delivery_system
        self.base_path = Path(__file__).parent.parent.parent / "spark" / "data"
        
        # Archivos CSV
        self.usuarios_csv = self.base_path / "usuarios.csv"
        self.restaurantes_csv = self.base_path / "restaurantes.csv"
        self.pedidos_csv = self.base_path / "pedidos.csv"
        
        # Datos cargados
        self.usuarios_data = []
        self.restaurantes_data = []
        self.pedidos_data = []
        self.calles_osm = []
        
        # Estadísticas
        self.stats = {
            'usuarios_cargados': 0,
            'restaurantes_cargados': 0,
            'pedidos_cargados': 0,
            'repartidores_generados': 0,
            'clientes_registrados': 0
        }
    
    def cargar_todos_los_datos(self, max_usuarios=200, max_pedidos=1000, num_repartidores=20):
        """Cargar todos los datos CSV y configurar el sistema completo"""
        log.info("Iniciando carga completa de datos CSV...")
        
        try:
            # 1. Inicializar datos OSM
            log.info("1. Inicializando datos OSM...")
            self.delivery_system.inicializar_datos_osm()
            
            # 2. Cargar calles OSM para generar coordenadas
            log.info("2. Cargando calles OSM...")
            self._cargar_calles_osm()
            
            # 3. Cargar datos CSV
            log.info("3. Cargando datos CSV...")
            self._cargar_usuarios_csv(max_usuarios)
            self._cargar_restaurantes_csv()
            self._cargar_pedidos_csv(max_pedidos)
            
            # 4. Registrar clientes en el sistema
            log.info("4. Registrando clientes...")
            self._registrar_clientes()
            
            # 5. Generar y registrar repartidores
            log.info("5. Generando repartidores...")
            self._generar_repartidores(num_repartidores)
            
            # 6. Crear pedidos en el sistema
            log.info("6. Creando pedidos...")
            self._crear_pedidos_sistema()
            
            log.info("Carga completa de datos finalizada")
            self._mostrar_estadisticas()
            
            return True
            
        except Exception as e:
            log.error(f"Error cargando datos: {e}")
            import traceback
            log.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _cargar_calles_osm(self):
        """Cargar calles OSM disponibles para generar coordenadas"""
        log.info("Cargando calles OSM...")
        
        with self.delivery_system.driver.session() as session:
            result = session.run("""
                MATCH (c:Calle)
                RETURN c.id as id, c.lat as lat, c.lon as lon, c.tipo as tipo
                LIMIT 1000
            """)
            
            self.calles_osm = [
                {
                    'id': record['id'],
                    'lat': record['lat'],
                    'lon': record['lon'],
                    'tipo': record.get('tipo', 'unknown')
                }
                for record in result
            ]
        
        log.info(f"Cargadas {len(self.calles_osm)} calles OSM")
    
    def _cargar_usuarios_csv(self, max_usuarios=200):
        """Cargar usuarios desde CSV"""
        log.info(f"Cargando usuarios desde {self.usuarios_csv}...")
        
        if not self.usuarios_csv.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {self.usuarios_csv}")
        
        with open(self.usuarios_csv, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for i, row in enumerate(reader):
                if i >= max_usuarios:
                    break
                
                # Solo cargar clientes (no admins ni chefs)
                if row['rol'] == 'Cliente':
                    # Generar coordenadas aleatorias basadas en calles OSM
                    calle_aleatoria = random.choice(self.calles_osm)
                    
                    # Añadir pequeña variación para simular direcciones específicas
                    lat_offset = random.uniform(-0.002, 0.002)  # ~200m variación
                    lon_offset = random.uniform(-0.002, 0.002)
                    
                    usuario = {
                        'id': int(row['id']),
                        'email': row['email'],
                        'rol': row['rol'],
                        'fecha_alta': row['fecha_alta'],
                        'lat': calle_aleatoria['lat'] + lat_offset,
                        'lon': calle_aleatoria['lon'] + lon_offset,
                        'nombre': row['email'].split('@')[0],  # Usar parte del email como nombre
                        'telefono': f"+506-{random.randint(1000,9999)}-{random.randint(1000,9999)}",
                        'direccion': f"Cerca de {calle_aleatoria['id']}, Cartago, Costa Rica"
                    }
                    self.usuarios_data.append(usuario)
        
        self.stats['usuarios_cargados'] = len(self.usuarios_data)
        log.info(f"Cargados {len(self.usuarios_data)} usuarios clientes")
    
    def _cargar_restaurantes_csv(self):
        """Cargar restaurantes desde CSV (ya tienen coordenadas)"""
        log.info(f"Cargando restaurantes desde {self.restaurantes_csv}...")
        
        if not self.restaurantes_csv.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {self.restaurantes_csv}")
        
        with open(self.restaurantes_csv, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                restaurante = {
                    'id': int(row['id']),
                    'nombre': row['nombre'],
                    'direccion': row['direccion'],
                    'telefono': row['telefono'],
                    'capacidad': int(row['capacidad']),
                    'categoria': row['categoria_local'],
                    'lat': float(row['lat']),
                    'lon': float(row['lon'])
                }
                self.restaurantes_data.append(restaurante)
        
        self.stats['restaurantes_cargados'] = len(self.restaurantes_data)
        log.info(f"Cargados {len(self.restaurantes_data)} restaurantes")
    
    def _cargar_pedidos_csv(self, max_pedidos=1000):
        """Cargar pedidos desde CSV"""
        log.info(f"Cargando pedidos desde {self.pedidos_csv}...")
        
        if not self.pedidos_csv.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {self.pedidos_csv}")
        
        # Crear mapas para validar IDs
        usuario_ids = {u['id'] for u in self.usuarios_data}
        restaurante_ids = {r['id'] for r in self.restaurantes_data}
        
        with open(self.pedidos_csv, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for i, row in enumerate(reader):
                if i >= max_pedidos:
                    break
                
                usuario_id = int(row['usuario_id'])
                restaurante_id = int(row['restaurante_id'])
                
                # Solo incluir pedidos de usuarios y restaurantes que tenemos
                if usuario_id in usuario_ids and restaurante_id in restaurante_ids:
                    # Solo pedidos PENDING o READY para simular entregas activas
                    if row['estado'] in ['PENDING', 'READY']:
                        pedido = {
                            'id': int(row['id']),
                            'menu_id': int(row['menu_id']),
                            'total': float(row['total']),
                            'estado': row['estado'],
                            'restaurante_id': restaurante_id,
                            'usuario_id': usuario_id,
                            'fecha_creacion': row['fecha_creacion'],
                            'items': [f"Item_{row['menu_id']}", f"Combo_{random.randint(1,5)}"]
                        }
                        self.pedidos_data.append(pedido)
        
        self.stats['pedidos_cargados'] = len(self.pedidos_data)
        log.info(f"Cargados {len(self.pedidos_data)} pedidos activos")
    
    def _registrar_clientes(self):
        """Registrar usuarios como clientes en el sistema de delivery"""
        log.info("Registrando clientes en el sistema...")
        
        for usuario in self.usuarios_data:
            cliente = Cliente(
                id=usuario['id'],
                nombre=usuario['nombre'],
                lat=usuario['lat'],
                lon=usuario['lon'],
                telefono=usuario['telefono'],
                direccion=usuario['direccion']
            )
            
            if self.delivery_system.registrar_cliente(cliente):
                self.stats['clientes_registrados'] += 1
        
        log.info(f"Registrados {self.stats['clientes_registrados']} clientes")
    
    def _generar_repartidores(self, num_repartidores=20):
        """Generar repartidores aleatorios en ubicaciones OSM"""
        log.info(f"Generando {num_repartidores} repartidores...")
        
        nombres_repartidores = [
            "Carlos Mendez", "Ana Rodriguez", "Miguel Santos", "Sofia Vargas",
            "Diego Morales", "Lucia Fernandez", "Javier Castro", "Maria Gonzalez",
            "Roberto Silva", "Carmen Jimenez", "Andres Herrera", "Valentina Cruz",
            "Fernando Rojas", "Isabella Ramirez", "Alejandro Torres", "Camila Flores",
            "Sebastian Gutierrez", "Daniela Moreno", "Nicolas Perez", "Gabriela Ruiz"
        ]
        
        for i in range(num_repartidores):
            # Ubicación aleatoria en una calle OSM
            calle_aleatoria = random.choice(self.calles_osm)
            
            repartidor = Repartidor(
                id=i + 1,
                nombre=nombres_repartidores[i] if i < len(nombres_repartidores) else f"Repartidor_{i+1}",
                lat=calle_aleatoria['lat'],
                lon=calle_aleatoria['lon'],
                activo=True,
                capacidad_max=random.randint(3, 7),
                velocidad_promedio=random.uniform(20.0, 30.0)
            )
            
            if self.delivery_system.registrar_repartidor(repartidor):
                self.stats['repartidores_generados'] += 1
        
        log.info(f"Generados {self.stats['repartidores_generados']} repartidores")
    
    def _crear_pedidos_sistema(self):
        """Crear pedidos en el sistema de delivery"""
        log.info("Creando pedidos en el sistema...")
        
        pedidos_creados = 0
        
        for pedido_data in self.pedidos_data:
            # Buscar cliente correspondiente
            cliente = None
            for c in self.delivery_system.clientes.values():
                if c.id == pedido_data['usuario_id']:
                    cliente = c
                    break
            
            if not cliente:
                continue
            
            # Convertir estado CSV a estado del sistema
            estado_map = {
                'PENDING': 'pendiente',
                'READY': 'pendiente',
                'PICKED_UP': 'en_ruta',
                'CANCELLED': 'cancelado'
            }
            
            pedido = Pedido(
                id=pedido_data['id'],
                cliente_id=pedido_data['usuario_id'],
                restaurante_id=pedido_data['restaurante_id'],
                items=pedido_data['items'],
                total=pedido_data['total'],
                estado=estado_map.get(pedido_data['estado'], 'pendiente'),
                tiempo_preparacion=random.randint(10, 25),
                prioridad=random.randint(1, 3),
                fecha_creacion=datetime.now() - timedelta(minutes=random.randint(5, 60))
            )
            
            if self.delivery_system.crear_pedido(pedido):
                pedidos_creados += 1
        
        log.info(f"Creados {pedidos_creados} pedidos en el sistema")
    
    def _mostrar_estadisticas(self):
        """Mostrar estadísticas de la carga de datos"""
        log.info("ESTADISTICAS DE CARGA DE DATOS:")
        log.info(f"   Usuarios cargados: {self.stats['usuarios_cargados']}")
        log.info(f"   Restaurantes cargados: {self.stats['restaurantes_cargados']}")
        log.info(f"   Pedidos cargados: {self.stats['pedidos_cargados']}")
        log.info(f"   Clientes registrados: {self.stats['clientes_registrados']}")
        log.info(f"   Repartidores generados: {self.stats['repartidores_generados']}")
        log.info(f"   Calles OSM disponibles: {len(self.calles_osm)}")
    
    def obtener_estadisticas(self) -> Dict:
        """Obtener estadísticas de la carga"""
        return {
            **self.stats,
            'calles_osm_disponibles': len(self.calles_osm),
            'usuarios_disponibles': len(self.usuarios_data),
            'restaurantes_disponibles': len(self.restaurantes_data),
            'pedidos_disponibles': len(self.pedidos_data)
        }

def cargar_datos_csv_completos():
    """Función principal para cargar todos los datos CSV"""
    log.info("Iniciando carga completa de datos CSV...")
    
    # Crear sistema de delivery
    delivery_system = DeliveryRoutesSystem()
    
    try:
        # Crear cargador
        loader = CSVDataLoader(delivery_system)
        
        # Cargar todos los datos
        success = loader.cargar_todos_los_datos(
            max_usuarios=150,      # Cargar 150 usuarios clientes
            max_pedidos=500,       # Cargar 500 pedidos activos
            num_repartidores=25    # Generar 25 repartidores
        )
        
        if success:
            # Guardar referencia del loader en el sistema para acceso desde API
            delivery_system._csv_loader = loader
            log.info("Sistema cargado exitosamente con datos CSV")
            return delivery_system
        else:
            log.error("Error cargando datos CSV")
            return None
            
    except Exception as e:
        log.error(f"Error en carga de datos: {e}")
        delivery_system.close()
        return None

if __name__ == "__main__":
    # Ejecutar carga de datos
    sistema = cargar_datos_csv_completos()
    
    if sistema:
        # Mostrar estado del sistema
        estado = sistema.obtener_estado_sistema()
        print("\n" + "="*50)
        print("ESTADO DEL SISTEMA CARGADO:")
        print("="*50)
        for key, value in estado.items():
            print(f"{key}: {value}")
        print("="*50)
        
        sistema.close()
    else:
        print("Error cargando el sistema") 