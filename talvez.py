#%%
import requests
import folium
from folium.plugins import MousePosition
from branca.element import Element
import math
from collections import deque
from folium.plugins import MarkerCluster
from branca.element import JavascriptLink
from ipyleaflet import Map, Marker, FullScreenControl, LayerGroup, Polyline
import ipywidgets as widgets
from IPython.display import display

# 1. Crear el mapa centrado en tu sector de Culiacán
m = Map(center=(24.805, -107.394), zoom=15)
m.add_control(FullScreenControl())

# Capa para los marcadores de clic
capa_interactiva = LayerGroup()
m.add_layer(capa_interactiva)

# Variables para guardar los IDs de los nodos para tu algoritmo
puntos_seleccionados = []
nodos_id_ruta = {"inicio": None, "meta": None}

def manejar_clic(**kwargs):
    if kwargs.get('type') == 'click':
        latlon = kwargs.get('coordinates')
        
        if len(puntos_seleccionados) < 2:
            puntos_seleccionados.append(latlon)
            
            # Buscamos el ID del nodo más cercano en tu grafo (usando tu función anterior)
            # Asegúrate de tener definida 'obtener_id_mas_cercano' y 'nodos_coords'
            nodo_id, _ = obtener_id_mas_cercano(latlon[0], latlon[1], nodos_coords)
            
            # Guardamos el ID según sea inicio o meta
            tipo = "INICIO" if len(puntos_seleccionados) == 1 else "META"
            if tipo == "INICIO": nodos_id_ruta["inicio"] = nodo_id
            else: nodos_id_ruta["meta"] = nodo_id

            # Marcador visual
            color = "green" if tipo == "INICIO" else "red"
            marcador = Marker(location=latlon, draggable=False, title=f"{tipo}: {nodo_id}")
            capa_interactiva.add_layer(marcador)
            
            print(f"✅ {tipo} capturado. ID Nodo OSM: {nodo_id}")

            if len(puntos_seleccionados) == 2:
                print("\n🚀 LISTO PARA CALCULAR RUTA")
                print(f"De: {nodos_id_ruta['inicio']} a {nodos_id_ruta['meta']}")

# Vincular evento
m.on_interaction(manejar_clic)

# Mostrar el mapa
display(m)


def crear_mapa_con_marcadores():
    centro = [24.796998, -107.387524]
    mapa = folium.Map(location=centro, zoom_start=15)
    
    # Solo cargamos el JS externo
    mapa.get_root().header.add_child(JavascriptLink("./script.js"))
    
    mapa.save("marcador_permanente.html")
    print("Mapa generado. El JS buscará el mapa automáticamente.")
crear_mapa_con_marcadores()

def llamar_openstreetmap(lat1, lon1, lat2, lon2):
    # 1. Configurar la URL (Formato: longitud,latitud)
    # Perfil 'driving' para rutas en auto
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    
    # 2. Parámetros para obtener todos los puntos del camino
    params = {
        'overview': 'full',    # Traer la ruta completa
        'geometries': 'geojson', # Formato fácil de leer en Python
        'steps': 'true'        # Traer las instrucciones paso a paso
    }

    try:
        print(f"Llamando a OpenStreetMap...")
        r = requests.get(url, params=params)
        
        if r.status_code == 200:
            data = r.json()
            
            # Extraer la ruta principal
            ruta = data['routes'][0]
            
            # ESTO ES LO QUE NECESITAS PARA TU TALLER:
            # Una lista de todas las coordenadas que forman el camino
            nodos = ruta['geometry']['coordinates']
            
            print(f"\n--- Datos obtenidos ---")
            print(f"Distancia total: {ruta['distance'] / 1000:.2f} km")
            print(f"Número de nodos encontrados: {len(nodos)}")
            
            print("\nPrimeros 5 nodos (puntos de intersección):")
            for i, punto in enumerate(nodos[:5]):
                # OSRM devuelve [longitud, latitud]
                print(f" Nodo {i}: Lat {punto[1]}, Lon {punto[0]}")
                
            return nodos
        else:
            print(f"Error en la llamada: {r.status_code}")
            return None

    except Exception as e:
        print(f"Error de conexión: {e}")
        return None
# %%
