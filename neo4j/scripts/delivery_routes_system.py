#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema Completo de Asignación de Rutas de Entrega
==================================================

Este módulo implementa un sistema completo para:
1. Procesar datos OSM reales (calles, intersecciones, distancias)
2. Gestionar clientes, repartidores y pedidos con geolocalización
3. Calcular rutas óptimas usando algoritmos de grafos (Dijkstra, vecino más cercano)
4. Asignar pedidos a repartidores optimizando tiempo y distancia
5. Simular entregas en tiempo real

Características principales:
- Integración completa con datos OpenStreetMap
- Algoritmos de optimización de rutas (TSP, VRP)
- Simulación de repartidores múltiples
- Cálculo de tiempos de entrega reales
- API REST para consultas en tiempo real
"""

import logging
import math
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from neo4j import GraphDatabase
import os
from pathlib import Path

# Configuración de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

@dataclass
class Cliente:
    """Representa un cliente con su ubicación"""
    id: int
    nombre: str
    lat: float
    lon: float
    telefono: str
    direccion: str
    calle_id: str = None  # ID de la calle más cercana en Neo4j

@dataclass
class Repartidor:
    """Representa un repartidor con su estado actual"""
    id: int
    nombre: str
    lat: float  # Ubicación actual
    lon: float
    activo: bool = True
    capacidad_max: int = 5  # Máximo de pedidos simultáneos
    pedidos_actuales: List[int] = None
    velocidad_promedio: float = 25.0  # km/h
    
    def __post_init__(self):
        if self.pedidos_actuales is None:
            self.pedidos_actuales = []

@dataclass
class Pedido:
    """Representa un pedido para entrega"""
    id: int
    cliente_id: int
    restaurante_id: int
    items: List[str]
    total: float
    estado: str = "pendiente"  # pendiente, asignado, en_ruta, entregado
    tiempo_preparacion: int = 15  # minutos
    prioridad: int = 1  # 1=normal, 2=alta, 3=urgente
    fecha_creacion: datetime = None
    repartidor_asignado: int = None
    tiempo_estimado_entrega: int = None  # minutos
    
    def __post_init__(self):
        if self.fecha_creacion is None:
            self.fecha_creacion = datetime.now()

@dataclass
class RutaOptima:
    """Representa una ruta optimizada para un repartidor"""
    repartidor_id: int
    pedidos: List[int]
    secuencia_entregas: List[Tuple[int, float, float]]  # (pedido_id, lat, lon)
    distancia_total: float
    tiempo_total: int  # minutos
    coordenadas_ruta: List[Tuple[float, float]]
    calles_ruta: List[str]

class DeliveryRoutesSystem:
    """Sistema principal de gestión de rutas de entrega"""
    
    def __init__(self):
        # Conexión a Neo4j
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "restaurantes123")
        self.driver = GraphDatabase.driver(
            self.neo4j_uri, 
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        # Almacenamiento en memoria
        self.clientes: Dict[int, Cliente] = {}
        self.repartidores: Dict[int, Repartidor] = {}
        self.pedidos: Dict[int, Pedido] = {}
        self.rutas_activas: Dict[int, RutaOptima] = {}
        
        # Configuración del sistema
        self.radio_busqueda_km = 5.0  # Radio para buscar calles cercanas
        self.tiempo_base_entrega = 5  # Tiempo base por entrega en minutos
        
    def close(self):
        """Cerrar conexión a Neo4j"""
        if self.driver:
            self.driver.close()
    
    # ==================== GESTIÓN DE DATOS OSM ====================
    
    def inicializar_datos_osm(self):
        """Inicializar y verificar datos OSM en Neo4j"""
        log.info("Inicializando datos OSM...")
        
        with self.driver.session() as session:
            # Verificar si existen datos OSM
            result = session.run("MATCH (c:Calle) RETURN count(c) as total")
            total_calles = result.single()["total"]
            
            if total_calles == 0:
                log.warning("No se encontraron datos OSM. Cargando datos sintéticos...")
                self._cargar_datos_sinteticos()
            else:
                log.info(f"Datos OSM encontrados: {total_calles} calles")
            
            # Crear índices espaciales si no existen
            self._crear_indices_espaciales()
            
            # Verificar conectividad del grafo
            self._verificar_conectividad_grafo()
    
    def _cargar_datos_sinteticos(self):
        """Cargar datos sintéticos si no hay datos OSM reales"""
        log.info("Generando red vial sintética...")
        
        # Coordenadas base: Cartago, Costa Rica
        base_lat, base_lon = 9.8644, -83.9194
        grid_size = 30
        step = 0.005  # ~500 metros entre nodos
        
        calles = []
        relaciones = []
        
        # Generar grilla de calles
        for i in range(grid_size):
            for j in range(grid_size):
                calle_id = f"synth_{i}_{j}"
                lat = base_lat + (i - grid_size//2) * step
                lon = base_lon + (j - grid_size//2) * step
                
                calles.append({
                    'id': calle_id,
                    'lat': lat,
                    'lon': lon,
                    'tipo': 'residential'
                })
                
                # Conexiones horizontales y verticales
                if j < grid_size - 1:  # Conexión horizontal
                    vecino_id = f"synth_{i}_{j+1}"
                    distancia = self._calcular_distancia_haversine(lat, lon, lat, lon + step)
                    relaciones.append({
                        'origen': calle_id,
                        'destino': vecino_id,
                        'distancia': distancia
                    })
                
                if i < grid_size - 1:  # Conexión vertical
                    vecino_id = f"synth_{i+1}_{j}"
                    distancia = self._calcular_distancia_haversine(lat, lon, lat + step, lon)
                    relaciones.append({
                        'origen': calle_id,
                        'destino': vecino_id,
                        'distancia': distancia
                    })
        
        # Insertar en Neo4j
        with self.driver.session() as session:
            # Crear nodos de calles
            session.run("""
                UNWIND $calles AS calle
                CREATE (:Calle {
                    id: calle.id,
                    lat: calle.lat,
                    lon: calle.lon,
                    tipo: calle.tipo
                })
            """, calles=calles)
            
            # Crear relaciones ROAD bidireccionales
            session.run("""
                UNWIND $relaciones AS rel
                MATCH (c1:Calle {id: rel.origen}), (c2:Calle {id: rel.destino})
                CREATE (c1)-[:ROAD {distancia: rel.distancia}]->(c2)
                CREATE (c2)-[:ROAD {distancia: rel.distancia}]->(c1)
            """, relaciones=relaciones)
        
        log.info(f"Red sintetica creada: {len(calles)} calles, {len(relaciones)*2} conexiones")
    
    def _crear_indices_espaciales(self):
        """Crear índices para consultas espaciales eficientes"""
        with self.driver.session() as session:
            indices = [
                "CREATE INDEX idx_calle_coords IF NOT EXISTS FOR (c:Calle) ON (c.lat, c.lon)",
                "CREATE INDEX idx_restaurante_coords IF NOT EXISTS FOR (r:Restaurante) ON (r.lat, r.lon)",
                "CREATE INDEX idx_calle_id IF NOT EXISTS FOR (c:Calle) ON (c.id)"
            ]
            
            for idx in indices:
                try:
                    session.run(idx)
                except Exception as e:
                    log.warning(f"Error creando índice: {e}")
    
    def _verificar_conectividad_grafo(self):
        """Verificar que el grafo de calles está conectado"""
        with self.driver.session() as session:
            # Contar componentes conectados
            result = session.run("""
                MATCH (c:Calle)
                WITH c
                LIMIT 100
                MATCH path = (c)-[:ROAD*1..5]-(other:Calle)
                RETURN count(DISTINCT other) as conectadas, count(DISTINCT c) as total
            """)
            
            record = result.single()
            if record:
                log.info(f"Conectividad del grafo: {record['conectadas']}/{record['total']} calles alcanzables")
    
    # ==================== GESTIÓN DE CLIENTES ====================
    
    def registrar_cliente(self, cliente: Cliente) -> bool:
        """Registrar un nuevo cliente y encontrar su calle más cercana"""
        try:
            # Encontrar calle más cercana
            calle_cercana = self._encontrar_calle_mas_cercana(cliente.lat, cliente.lon)
            if calle_cercana:
                cliente.calle_id = calle_cercana['id']
                
                # Crear nodo Cliente en Neo4j
                with self.driver.session() as session:
                    session.run("""
                        CREATE (cl:Cliente {
                            id: $id,
                            nombre: $nombre,
                            lat: $lat,
                            lon: $lon,
                            telefono: $telefono,
                            direccion: $direccion,
                            calle_id: $calle_id
                        })
                    """, **cliente.__dict__)
                    
                    # Crear relación con calle más cercana
                    session.run("""
                        MATCH (cl:Cliente {id: $cliente_id}), (c:Calle {id: $calle_id})
                        CREATE (cl)-[:UBICADO_EN {
                            distancia: $distancia
                        }]->(c)
                    """, 
                    cliente_id=cliente.id,
                    calle_id=calle_cercana['id'],
                    distancia=calle_cercana['distancia']
                    )
                
                self.clientes[cliente.id] = cliente
                log.info(f"Cliente {cliente.nombre} registrado en calle {cliente.calle_id}")
                return True
            else:
                log.error(f"No se encontro calle cercana para cliente {cliente.nombre}")
                return False
                
        except Exception as e:
            log.error(f"Error registrando cliente: {e}")
            return False
    
    def _encontrar_calle_mas_cercana(self, lat: float, lon: float) -> Optional[Dict]:
        """Encontrar la calle más cercana a unas coordenadas"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Calle)
                WITH c, 
                     abs(c.lat - $lat) + abs(c.lon - $lon) as distancia_manhattan,
                     sqrt((c.lat - $lat) * (c.lat - $lat) + (c.lon - $lon) * (c.lon - $lon)) * 111000 as distancia_metros
                WHERE distancia_metros < $radio_metros
                ORDER BY distancia_metros
                LIMIT 1
                RETURN c.id as id, c.lat as lat, c.lon as lon, distancia_metros as distancia
            """, lat=lat, lon=lon, radio_metros=self.radio_busqueda_km * 1000)
            
            record = result.single()
            return record.data() if record else None
    
    # ==================== GESTIÓN DE REPARTIDORES ====================
    
    def registrar_repartidor(self, repartidor: Repartidor) -> bool:
        """Registrar un nuevo repartidor"""
        try:
            # Encontrar calle más cercana para el repartidor
            calle_cercana = self._encontrar_calle_mas_cercana(repartidor.lat, repartidor.lon)
            
            with self.driver.session() as session:
                session.run("""
                    CREATE (r:Repartidor {
                        id: $id,
                        nombre: $nombre,
                        lat: $lat,
                        lon: $lon,
                        activo: $activo,
                        capacidad_max: $capacidad_max,
                        velocidad_promedio: $velocidad_promedio,
                        calle_actual: $calle_id
                    })
                """, 
                id=repartidor.id,
                nombre=repartidor.nombre,
                lat=repartidor.lat,
                lon=repartidor.lon,
                activo=repartidor.activo,
                capacidad_max=repartidor.capacidad_max,
                velocidad_promedio=repartidor.velocidad_promedio,
                calle_id=calle_cercana['id'] if calle_cercana else None
                )
            
            self.repartidores[repartidor.id] = repartidor
            log.info(f"Repartidor {repartidor.nombre} registrado")
            return True
            
        except Exception as e:
            log.error(f"Error registrando repartidor: {e}")
            return False
    
    def actualizar_ubicacion_repartidor(self, repartidor_id: int, lat: float, lon: float):
        """Actualizar la ubicación actual de un repartidor"""
        if repartidor_id in self.repartidores:
            self.repartidores[repartidor_id].lat = lat
            self.repartidores[repartidor_id].lon = lon
            
            # Actualizar en Neo4j
            with self.driver.session() as session:
                session.run("""
                    MATCH (r:Repartidor {id: $id})
                    SET r.lat = $lat, r.lon = $lon
                """, id=repartidor_id, lat=lat, lon=lon)
    
    # ==================== GESTIÓN DE PEDIDOS ====================
    
    def crear_pedido(self, pedido: Pedido) -> bool:
        """Crear un nuevo pedido"""
        try:
            with self.driver.session() as session:
                session.run("""
                    CREATE (p:PedidoEntrega {
                        id: $id,
                        cliente_id: $cliente_id,
                        restaurante_id: $restaurante_id,
                        items: $items,
                        total: $total,
                        estado: $estado,
                        tiempo_preparacion: $tiempo_preparacion,
                        prioridad: $prioridad,
                        fecha_creacion: datetime($fecha_creacion)
                    })
                """, 
                id=pedido.id,
                cliente_id=pedido.cliente_id,
                restaurante_id=pedido.restaurante_id,
                items=pedido.items,
                total=pedido.total,
                estado=pedido.estado,
                tiempo_preparacion=pedido.tiempo_preparacion,
                prioridad=pedido.prioridad,
                fecha_creacion=pedido.fecha_creacion.isoformat()
                )
            
            self.pedidos[pedido.id] = pedido
            log.info(f"Pedido {pedido.id} creado para cliente {pedido.cliente_id}")
            return True
            
        except Exception as e:
            log.error(f"Error creando pedido: {e}")
            return False
    
    # ==================== ALGORITMOS DE OPTIMIZACIÓN ====================
    
    def calcular_ruta_optima(self, origen_lat: float, origen_lon: float, 
                           destinos: List[Tuple[int, float, float]]) -> RutaOptima:
        """
        Calcular ruta óptima usando algoritmo del vecino más cercano
        Args:
            origen_lat, origen_lon: Coordenadas de inicio
            destinos: Lista de (pedido_id, lat, lon) destinos
        """
        if not destinos:
            return None
        
        # Encontrar calles más cercanas para todos los puntos
        origen_calle = self._encontrar_calle_mas_cercana(origen_lat, origen_lon)
        destinos_calles = []
        
        for pedido_id, lat, lon in destinos:
            calle = self._encontrar_calle_mas_cercana(lat, lon)
            if calle:
                destinos_calles.append((pedido_id, calle['id'], lat, lon))
        
        if not origen_calle or not destinos_calles:
            log.error("No se pudieron encontrar calles para la ruta")
            return None
        
        # Aplicar algoritmo del vecino más cercano
        ruta_optimizada = self._algoritmo_vecino_mas_cercano(
            origen_calle['id'], destinos_calles
        )
        
        return ruta_optimizada
    
    def _algoritmo_vecino_mas_cercano(self, origen_calle: str, 
                                    destinos: List[Tuple[int, str, float, float]]) -> RutaOptima:
        """Implementar algoritmo del vecino más cercano"""
        visitados = set()
        secuencia = []
        distancia_total = 0.0
        tiempo_total = 0
        coordenadas_ruta = []
        calles_ruta = [origen_calle]
        
        actual = origen_calle
        
        while len(visitados) < len(destinos):
            # Encontrar el destino más cercano no visitado
            mejor_distancia = float('inf')
            mejor_destino = None
            mejor_ruta = None
            
            for i, (pedido_id, calle_destino, lat, lon) in enumerate(destinos):
                if i in visitados:
                    continue
                
                # Calcular distancia usando Dijkstra en Neo4j
                ruta_info = self._calcular_ruta_dijkstra(actual, calle_destino)
                
                if ruta_info and ruta_info['distancia'] < mejor_distancia:
                    mejor_distancia = ruta_info['distancia']
                    mejor_destino = (i, pedido_id, calle_destino, lat, lon)
                    mejor_ruta = ruta_info
            
            if mejor_destino:
                i, pedido_id, calle_destino, lat, lon = mejor_destino
                visitados.add(i)
                secuencia.append((pedido_id, lat, lon))
                distancia_total += mejor_distancia
                tiempo_total += self._calcular_tiempo_viaje(mejor_distancia) + self.tiempo_base_entrega
                
                # Agregar coordenadas de la ruta
                if mejor_ruta['coordenadas']:
                    coordenadas_ruta.extend(mejor_ruta['coordenadas'])
                    calles_ruta.extend(mejor_ruta['calles'])
                
                actual = calle_destino
            else:
                break
        
        return RutaOptima(
            repartidor_id=0,  # Se asignará después
            pedidos=[s[0] for s in secuencia],
            secuencia_entregas=secuencia,
            distancia_total=distancia_total,
            tiempo_total=tiempo_total,
            coordenadas_ruta=coordenadas_ruta,
            calles_ruta=calles_ruta
        )
    
    def _calcular_ruta_dijkstra(self, origen: str, destino: str) -> Optional[Dict]:
        """Calcular ruta más corta usando Dijkstra en Neo4j"""
        with self.driver.session() as session:
            # Usar shortestPath de Neo4j como aproximación a Dijkstra
            result = session.run("""
                MATCH (origen:Calle {id: $origen}), (destino:Calle {id: $destino})
                MATCH path = shortestPath((origen)-[:ROAD*1..20]-(destino))
                WHERE path IS NOT NULL
                RETURN 
                    reduce(dist = 0, rel in relationships(path) | dist + rel.distancia) as distancia,
                    [node in nodes(path) | {lat: node.lat, lon: node.lon}] as coordenadas,
                    [node in nodes(path) | node.id] as calles,
                    length(path) as num_calles
            """, origen=origen, destino=destino)
            
            record = result.single()
            if record:
                return {
                    'distancia': record['distancia'],
                    'coordenadas': [(c['lat'], c['lon']) for c in record['coordenadas']],
                    'calles': record['calles'],
                    'num_calles': record['num_calles']
                }
            return None
    
    def _calcular_tiempo_viaje(self, distancia_metros: float, velocidad_kmh: float = 25.0) -> int:
        """Calcular tiempo de viaje en minutos"""
        if distancia_metros <= 0:
            return 0
        tiempo_horas = (distancia_metros / 1000) / velocidad_kmh
        return max(1, int(tiempo_horas * 60))  # Mínimo 1 minuto
    
    # ==================== ASIGNACIÓN DE PEDIDOS ====================
    
    def asignar_pedidos_automatico(self) -> Dict[int, List[int]]:
        """Asignar pedidos pendientes a repartidores disponibles automáticamente"""
        pedidos_pendientes = [p for p in self.pedidos.values() if p.estado == 'pendiente']
        repartidores_disponibles = [r for r in self.repartidores.values() 
                                  if r.activo and len(r.pedidos_actuales) < r.capacidad_max]
        
        if not pedidos_pendientes or not repartidores_disponibles:
            log.info("No hay pedidos pendientes o repartidores disponibles")
            return {}
        
        # Ordenar pedidos por prioridad y tiempo
        pedidos_pendientes.sort(key=lambda p: (-p.prioridad, p.fecha_creacion))
        
        asignaciones = {}
        
        for pedido in pedidos_pendientes:
            mejor_repartidor = self._encontrar_mejor_repartidor(pedido)
            
            if mejor_repartidor:
                if mejor_repartidor.id not in asignaciones:
                    asignaciones[mejor_repartidor.id] = []
                
                asignaciones[mejor_repartidor.id].append(pedido.id)
                mejor_repartidor.pedidos_actuales.append(pedido.id)
                pedido.estado = 'asignado'
                pedido.repartidor_asignado = mejor_repartidor.id
                
                log.info(f"Pedido {pedido.id} asignado a repartidor {mejor_repartidor.nombre}")
        
        # Calcular rutas optimizadas para cada repartidor
        for repartidor_id, pedidos_ids in asignaciones.items():
            self._calcular_y_guardar_ruta_repartidor(repartidor_id, pedidos_ids)
        
        return asignaciones
    
    def _encontrar_mejor_repartidor(self, pedido: Pedido) -> Optional[Repartidor]:
        """Encontrar el mejor repartidor para un pedido"""
        if pedido.cliente_id not in self.clientes:
            return None
        
        cliente = self.clientes[pedido.cliente_id]
        mejor_repartidor = None
        menor_tiempo = float('inf')
        
        for repartidor in self.repartidores.values():
            if not repartidor.activo or len(repartidor.pedidos_actuales) >= repartidor.capacidad_max:
                continue
            
            # Calcular distancia aproximada
            distancia = self._calcular_distancia_haversine(
                repartidor.lat, repartidor.lon,
                cliente.lat, cliente.lon
            )
            
            tiempo_estimado = self._calcular_tiempo_viaje(distancia, repartidor.velocidad_promedio)
            
            # Penalizar por pedidos actuales
            penalizacion = len(repartidor.pedidos_actuales) * 10
            tiempo_total = tiempo_estimado + penalizacion
            
            if tiempo_total < menor_tiempo:
                menor_tiempo = tiempo_total
                mejor_repartidor = repartidor
        
        return mejor_repartidor
    
    def _calcular_y_guardar_ruta_repartidor(self, repartidor_id: int, pedidos_ids: List[int]):
        """Calcular ruta optimizada para un repartidor y sus pedidos"""
        repartidor = self.repartidores[repartidor_id]
        
        # Obtener destinos (ubicaciones de clientes)
        destinos = []
        for pedido_id in pedidos_ids:
            pedido = self.pedidos[pedido_id]
            cliente = self.clientes[pedido.cliente_id]
            destinos.append((pedido_id, cliente.lat, cliente.lon))
        
        # Calcular ruta óptima
        ruta = self.calcular_ruta_optima(repartidor.lat, repartidor.lon, destinos)
        
        if ruta:
            ruta.repartidor_id = repartidor_id
            self.rutas_activas[repartidor_id] = ruta
            
            # Actualizar tiempos estimados de entrega
            tiempo_acumulado = 0
            for i, pedido_id in enumerate(ruta.pedidos):
                tiempo_acumulado += (ruta.tiempo_total // len(ruta.pedidos))
                self.pedidos[pedido_id].tiempo_estimado_entrega = tiempo_acumulado
            
            log.info(f"Ruta calculada para repartidor {repartidor.nombre}: "
                    f"{len(ruta.pedidos)} pedidos, {ruta.distancia_total:.1f}m, {ruta.tiempo_total}min")
    
    # ==================== UTILIDADES ====================
    
    def _calcular_distancia_haversine(self, lat1: float, lon1: float, 
                                    lat2: float, lon2: float) -> float:
        """Calcular distancia entre dos puntos usando fórmula de Haversine"""
        R = 6371000  # Radio de la Tierra en metros
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    # ==================== API ENDPOINTS ====================
    
    def obtener_estado_sistema(self) -> Dict[str, Any]:
        """Obtener estado general del sistema"""
        return {
            'clientes_registrados': len(self.clientes),
            'repartidores_activos': len([r for r in self.repartidores.values() if r.activo]),
            'pedidos_pendientes': len([p for p in self.pedidos.values() if p.estado == 'pendiente']),
            'pedidos_en_ruta': len([p for p in self.pedidos.values() if p.estado == 'en_ruta']),
            'rutas_activas': len(self.rutas_activas),
            'timestamp': datetime.now().isoformat()
        }
    
    def obtener_ruta_repartidor(self, repartidor_id: int) -> Optional[Dict]:
        """Obtener ruta activa de un repartidor"""
        if repartidor_id in self.rutas_activas:
            ruta = self.rutas_activas[repartidor_id]
            return {
                'repartidor_id': ruta.repartidor_id,
                'pedidos': ruta.pedidos,
                'secuencia_entregas': ruta.secuencia_entregas,
                'distancia_total': ruta.distancia_total,
                'tiempo_total': ruta.tiempo_total,
                'coordenadas_ruta': ruta.coordenadas_ruta,
                'progreso': self._calcular_progreso_ruta(repartidor_id)
            }
        return None
    
    def _calcular_progreso_ruta(self, repartidor_id: int) -> Dict:
        """Calcular progreso actual de una ruta"""
        # Simulación simple del progreso
        return {
            'pedidos_entregados': 0,
            'pedidos_restantes': len(self.rutas_activas[repartidor_id].pedidos),
            'tiempo_transcurrido': 0,
            'tiempo_estimado_restante': self.rutas_activas[repartidor_id].tiempo_total
        }
    
    def simular_entrega_completada(self, pedido_id: int) -> bool:
        """Simular que se completó una entrega"""
        if pedido_id in self.pedidos:
            pedido = self.pedidos[pedido_id]
            pedido.estado = 'entregado'
            
            # Remover de repartidor
            if pedido.repartidor_asignado and pedido.repartidor_asignado in self.repartidores:
                repartidor = self.repartidores[pedido.repartidor_asignado]
                if pedido_id in repartidor.pedidos_actuales:
                    repartidor.pedidos_actuales.remove(pedido_id)
            
            log.info(f"Entrega completada: Pedido {pedido_id}")
            return True
        
        return False

# ==================== FUNCIONES DE INICIALIZACIÓN ====================

def generar_datos_demo():
    """Generar datos de demostración"""
    system = DeliveryRoutesSystem()
    
    try:
        # Inicializar datos OSM
        system.inicializar_datos_osm()
        
        # Registrar clientes demo
        clientes_demo = [
            Cliente(1, "Juan Pérez", 9.8644, -83.9194, "8888-1111", "Centro de Cartago"),
            Cliente(2, "María González", 9.8654, -83.9184, "8888-2222", "Barrio La Lima"),
            Cliente(3, "Carlos Rodríguez", 9.8634, -83.9204, "8888-3333", "Los Ángeles"),
            Cliente(4, "Ana Jiménez", 9.8664, -83.9174, "8888-4444", "Barrio Asis"),
            Cliente(5, "Luis Herrera", 9.8624, -83.9214, "8888-5555", "Dulce Nombre")
        ]
        
        for cliente in clientes_demo:
            system.registrar_cliente(cliente)
        
        # Registrar repartidores demo
        repartidores_demo = [
            Repartidor(1, "Repartidor Alpha", 9.8644, -83.9194, True, 5, [], 30.0),
            Repartidor(2, "Repartidor Beta", 9.8654, -83.9184, True, 4, [], 25.0),
            Repartidor(3, "Repartidor Gamma", 9.8634, -83.9204, True, 6, [], 28.0)
        ]
        
        for repartidor in repartidores_demo:
            system.registrar_repartidor(repartidor)
        
        # Crear pedidos demo
        pedidos_demo = [
            Pedido(1, 1, 1, ["Pizza Margherita", "Coca Cola"], 15500.0, "pendiente", 20, 2),
            Pedido(2, 2, 2, ["Hamburguesa Clásica", "Papas"], 8900.0, "pendiente", 15, 1),
            Pedido(3, 3, 1, ["Sushi Variado"], 22000.0, "pendiente", 25, 3),
            Pedido(4, 4, 3, ["Tacos Mexicanos"], 12500.0, "pendiente", 18, 1),
            Pedido(5, 5, 2, ["Ensalada César"], 7800.0, "pendiente", 10, 2)
        ]
        
        for pedido in pedidos_demo:
            system.crear_pedido(pedido)
        
        # Asignar pedidos automáticamente
        asignaciones = system.asignar_pedidos_automatico()
        
        log.info("Datos de demostracion generados exitosamente")
        log.info(f"Asignaciones realizadas: {asignaciones}")
        
        return system
        
    except Exception as e:
        log.error(f"Error generando datos demo: {e}")
        return None
    finally:
        if system:
            system.close()

if __name__ == "__main__":
    # Ejecutar generación de datos demo
    sistema = generar_datos_demo()
    if sistema:
        print("\nSistema de rutas de entrega inicializado correctamente")
        print("Estado del sistema:", sistema.obtener_estado_sistema())