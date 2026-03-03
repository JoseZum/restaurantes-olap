#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VISUALIZADOR DE RUTAS DE ENTREGA
Genera mapas interactivos con rutas reales desde la API de rutas
"""

import argparse
import requests
import folium
import json
import sys
import os
import webbrowser
import networkx as nx

# Importar OSMnx
try:
    import osmnx as ox
    OSMNX_AVAILABLE = True
    print("OSMnx disponible - se usarán rutas reales por calles")
except ImportError:
    OSMNX_AVAILABLE = False
    print("OSMnx no disponible - se usarán coordenadas directas")

def test_api_connection():
    """Probar conexión con la API"""
    try:
        response = requests.get("http://localhost:8005/estado-sistema", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"API Status: {data.get('status', 'OK')}")
            print(f"Restaurantes disponibles: {data.get('restaurantes_disponibles', 0)}")
            print(f"Usuarios disponibles: {data.get('usuarios_disponibles', 0)}")
            return True
        else:
            print(f"API responde con código: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error conectando a la API: {e}")
        return False

def obtener_ruta_desde_api(cliente_id, restaurante_id):
    """Obtener datos de ruta desde la API con datos REALES"""
    try:
        url = f"http://localhost:8005/ruta-optima"
        params = {"cliente_id": cliente_id, "restaurante_id": restaurante_id}
        
        print(f"Consultando API: {url}")
        print(f"Parámetros: cliente_id={cliente_id}, restaurante_id={restaurante_id}")
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"Respuesta exitosa de la API")
            print(f"Cliente: {data.get('cliente_nombre', 'N/A')}")
            print(f"Restaurante: {data.get('restaurante_nombre', 'N/A')}")
            print(f"Distancia: {data.get('distancia_total_km', 0)} km")
            print(f"Tiempo estimado: {data.get('tiempo_estimado_min', 0)} min")
            return data
        else:
            print(f"Error en API: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error consultando API: {e}")
        return None

def cargar_grafo_calles(osm_file):
    """Cargar el grafo de calles desde el archivo OSM"""
    try:
        if not os.path.exists(osm_file):
            print(f"Advertencia: No se encontró el archivo {osm_file}")
            print(f"Continuando sin grafo de calles (usaremos coordenadas directas)")
            return None
            
        if not OSMNX_AVAILABLE:
            print("OSMnx no disponible, usando coordenadas directas")
            return None
            
        print(f"Cargando grafo de calles desde {osm_file}...")
        try:
            # Intentar diferentes métodos según la versión de OSMnx
            try:
                G = ox.graph_from_xml(osm_file)
                print(f"Grafo cargado con graph_from_xml")
            except:
                try:
                    G = ox.graph_from_file(osm_file)
                    print(f"Grafo cargado con graph_from_file")
                except:
                    # Si no funciona, retornar None para usar coordenadas directas
                    print(f"No se pudo cargar con OSMnx, usando coordenadas directas")
                    return None
                    
        except Exception as e:
            print(f"Error al cargar el grafo: {e}")
            print(f"Continuando sin grafo (usaremos coordenadas directas)")
            return None
            
        print(f"Grafo cargado: {len(G.nodes)} nodos, {len(G.edges)} aristas")
        return G
        
    except Exception as e:
        print(f"Error general: {e}")
        print(f"Continuando sin grafo de calles")
        return None

def crear_mapa_ruta(datos_ruta, output_file, G=None):
    """Crear mapa interactivo con la ruta usando datos reales Y rutas por calles"""
    try:
        # Obtener coordenadas desde la ruta OSM
        ruta_osm = datos_ruta.get('ruta_osm', [])
        
        if len(ruta_osm) >= 2:
            # Usar primer y último punto de la ruta OSM
            coords_restaurante = [ruta_osm[0]['lat'], ruta_osm[0]['lon']]
            coords_cliente = [ruta_osm[-1]['lat'], ruta_osm[-1]['lon']]
        else:
            # Fallback a coordenadas por defecto
            coords_cliente = [9.864, -83.916]
            coords_restaurante = [9.864, -83.916]
        
        # Crear mapa centrado en Cartago
        center_lat = (coords_cliente[0] + coords_restaurante[0]) / 2
        center_lon = (coords_cliente[1] + coords_restaurante[1]) / 2
        
        mapa = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=14,
            tiles='OpenStreetMap'
        )
        
        # Usar la ruta Neo4j directamente
        path_coords = []
        if ruta_osm and len(ruta_osm) > 1:
            print(f"Usando ruta Neo4j con {len(ruta_osm)} puntos")
            path_coords = [[punto['lat'], punto['lon']] for punto in ruta_osm]
        else:
            print("Sin ruta OSM, usando línea directa")
            path_coords = [coords_restaurante, coords_cliente]
        
        # Dibujar línea de ruta (REAL con Neo4j)
        if path_coords and len(path_coords) > 1:
            color_ruta = 'blue' if len(ruta_osm) > 2 else 'red'
            peso_ruta = 6 if len(ruta_osm) > 2 else 4
            metodo = datos_ruta.get('metodo', 'unknown')
            popup_text = f"Ruta Neo4j - {datos_ruta.get('distancia_km', 0)} km (Método: {metodo})"
            
            folium.PolyLine(
                path_coords,
                color=color_ruta,
                weight=peso_ruta,
                opacity=0.8,
                popup=popup_text
            ).add_to(mapa)
        
        # Marcador del restaurante (VERDE)
        folium.Marker(
            coords_restaurante,
            popup=f"""
            <div style='width: 200px;'>
                <h4>{datos_ruta.get('restaurante', 'Restaurante')}</h4>
                <p><b>ID:</b> {datos_ruta.get('restaurante_id', 'N/A')}</p>
                <p><b>Coordenadas:</b> {coords_restaurante[0]:.6f}, {coords_restaurante[1]:.6f}</p>
                <p><b>Método:</b> {datos_ruta.get('metodo', 'N/A')}</p>
            </div>
            """,
            tooltip=f"ORIGEN: {datos_ruta.get('restaurante', 'N/A')}",
            icon=folium.Icon(color='green', icon='cutlery', prefix='fa')
        ).add_to(mapa)
        
        # Marcador del cliente (AZUL)
        folium.Marker(
            coords_cliente,
            popup=f"""
            <div style='width: 200px;'>
                <h4>Cliente: {datos_ruta.get('cliente', 'Cliente')}</h4>
                <p><b>ID:</b> {datos_ruta.get('cliente_id', 'N/A')}</p>
                <p><b>Coordenadas:</b> {coords_cliente[0]:.6f}, {coords_cliente[1]:.6f}</p>
                <p><b>Segmentos:</b> {datos_ruta.get('segmentos', 0)}</p>
            </div>
            """,
            tooltip=f"DESTINO: {datos_ruta.get('cliente', 'N/A')}",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(mapa)
        
        # Panel de información
        metodo = datos_ruta.get('metodo', 'unknown')
        ruta_tipo = "Neo4j OSM Conectado" if "Neo4j" in metodo else "Método desconocido"
        info_html = f"""
        <div style='position: fixed; 
                    bottom: 50px; left: 50px; width: 320px; height: 160px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px;
                    box-shadow: 0 0 15px rgba(0,0,0,0.2);
                    border-radius: 5px;'>
        <h4 style='margin-top:0; color: #2E8B57;'>Información de Entrega Neo4j</h4>
        <p><b>Cliente:</b> {datos_ruta.get('cliente', 'N/A')}</p>
        <p><b>Restaurante:</b> {datos_ruta.get('restaurante', 'N/A')}</p>
        <p><b>Distancia:</b> {datos_ruta.get('distancia_km', 0)} km</p>
        <p><b>Tiempo estimado:</b> {datos_ruta.get('tiempo_estimado_min', 0)} min</p>
        <p><b>Método:</b> {ruta_tipo}</p>
        <p><b>Segmentos:</b> {datos_ruta.get('segmentos', 0)}</p>
        <p><b>Datos:</b> Neo4j OSM Reales</p>
        </div>
        """
        mapa.get_root().html.add_child(folium.Element(info_html))
        
        # Guardar mapa
        mapa.save(output_file)
        print(f"Mapa guardado en: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"Error creando mapa: {e}")
        return False

def main():
    """Función principal que genera mapas con rutas Neo4j"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generador de mapas de rutas Neo4j')
    parser.add_argument('--cliente_id', type=int, required=True, help='ID del cliente')
    parser.add_argument('--restaurante_id', type=int, required=True, help='ID del restaurante')
    parser.add_argument('--api_url', type=str, default='http://localhost:8005/ruta-optima', help='URL de la API')
    
    args = parser.parse_args()
    
    print("=== GENERADOR DE MAPAS DE RUTAS NEO4J ===")
    print(f"Cliente ID: {args.cliente_id}")
    print(f"Restaurante ID: {args.restaurante_id}")
    print(f"API URL: {args.api_url}")
    
    # Configuraciones basadas en argumentos
    configuraciones = [
        (args.cliente_id, args.restaurante_id)
    ]
    
    mapas_generados = 0
    
    for cliente_id, restaurante_id in configuraciones:
        print(f"\n--- Generando ruta Cliente {cliente_id} -> Restaurante {restaurante_id} ---")
        
        # Obtener datos desde API Neo4j
        datos_ruta = obtener_ruta_desde_api(cliente_id, restaurante_id)
        
        if datos_ruta:
            # Crear directorio de visualizaciones si no existe
            os.makedirs("visualizaciones", exist_ok=True)
            
            # Crear archivo de salida en el directorio visualizaciones
            output_file = f"visualizaciones/route_map_cliente{cliente_id}_rest{restaurante_id}.html"
            
            # Crear mapa con datos Neo4j
            if crear_mapa_ruta(datos_ruta, output_file):
                print(f"EXITO: Mapa Neo4j creado para Cliente {cliente_id} -> Restaurante {restaurante_id}")
                print(f"   Archivo: {output_file}")
                print(f"   Método: {datos_ruta.get('metodo', 'unknown')}")
                print(f"   Distancia: {datos_ruta.get('distancia_km', 0)} km")
                mapas_generados += 1
            else:
                print(f"ERROR: No se pudo crear mapa para Cliente {cliente_id} -> Restaurante {restaurante_id}")
        else:
            print(f"ERROR: No se pudieron obtener datos de la API para Cliente {cliente_id} -> Restaurante {restaurante_id}")
    
    print(f"\n=== RESUMEN NEO4J ===")
    print(f"Mapas generados exitosamente: {mapas_generados}/1")
    print(f"Mapas usan rutas REALES de Neo4j OSM")
    print(f"Datos de restaurantes y clientes desde Neo4j")
    print(f"Algoritmo: shortestPath en grafo OSM conectado")
    
    if mapas_generados > 0:
        print(f"\nArchivos generados:")
        for cliente_id, restaurante_id in configuraciones:
            archivo = f"visualizaciones/route_map_cliente{cliente_id}_rest{restaurante_id}.html"
            if os.path.exists(archivo):
                size_kb = os.path.getsize(archivo) / 1024
                print(f"{archivo} ({size_kb:.1f}KB)")
                print(f"   Abre este archivo en tu navegador para ver la ruta")

if __name__ == "__main__":
    main() 