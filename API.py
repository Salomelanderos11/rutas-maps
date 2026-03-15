import requests
import folium
from folium.plugins import MousePosition
from branca.element import Element
import math
from collections import deque
from folium.plugins import MarkerCluster

sur = 24.796998
oeste = -107.401461
norte = 24.812974
este= -107.387524
def extraer_nodos_sector(south, west, north, east):
    url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:60];
    (way["highway"~"primary|secondary|tertiary|residential"]({south},{west},{north},{east}););
    out body; >; out skel qt;
    """
    r = requests.post(url, data={'data': query})
    if r.status_code == 200:
        return r.json().get('elements', []) # Retorna la lista con TODO (nodos y ways)
    return []

data = extraer_nodos_sector(sur, oeste, norte,este)
nodos_sector = [e for e in data if e['type'] == 'node']



def calcular_distancia(p1, p2):
    # Fórmula de Haversine para distancia entre coordenadas (en metros)
    lat1, lon1 = p1
    lat2, lon2 = p2
    radio_tierra = 6371000  
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return radio_tierra * c


def construir_grafo(data):
    grafo = {}
    elementos = data

    # 1. Mapear primero todos los nodos para tener sus coordenadas
    nodos_coords = {e['id']: (e['lat'], e['lon']) for e in elementos if e['type'] == 'node'}

    # 2. Procesar los 'ways' para crear las conexiones (aristas)
    for ele in elementos:
        if ele['type'] == 'way':
            # Lista de IDs de nodos que forman esta calle específica
            nodos_en_calle = ele.get('nodes', [])
            
            for i in range(len(nodos_en_calle) - 1):
                u = nodos_en_calle[i]
                v = nodos_en_calle[i+1]

                # Solo conectamos si ambos nodos están en nuestro mapeo
                if u in nodos_coords and v in nodos_coords:
                    dist = calcular_distancia(nodos_coords[u], nodos_coords[v])
                    
                    # Inicializar nodos en el grafo si no existen
                    if u not in grafo: grafo[u] = {'lat': nodos_coords[u][0], 'lon': nodos_coords[u][1], 'vecinos': []}
                    if v not in grafo: grafo[v] = {'lat': nodos_coords[v][0], 'lon': nodos_coords[v][1], 'vecinos': []}

                    # Crear la conexión (Arista)
                    grafo[u]['vecinos'].append({'id': v, 'peso': dist})
                    grafo[v]['vecinos'].append({'id': u, 'peso': dist})
    
    return grafo

grafocompleto= construir_grafo(data)





def buscar_ruta_bfs(grafo, inicio_id, meta_id):
  
    # 1. Cola para BFS: guarda el (nodo_actual, camino_recorrido)
    cola = deque([(inicio_id, [inicio_id])])
    
    # 2. Conjunto de visitados para evitar ciclos infinitos
    visitados = {inicio_id}

    while cola:
        (nodo_actual, camino) = cola.popleft()

        # ¿Llegamos a la meta?
        if nodo_actual == meta_id:
            print("bfs exito")
            return camino

        # Explorar vecinos
        # VALIDACIÓN 3: Verificar que el nodo actual tenga la llave 'vecinos'
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                
                # VALIDACIÓN 4: Solo procesar el vecino si existe en el grafo
                # Esto evita el KeyError si el vecino está fuera del sector (Bounding Box)
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    
                    # Creamos el nuevo camino (forma eficiente de copiar lista)
                    nuevo_camino = camino + [vecino_id]
                    cola.append((vecino_id, nuevo_camino))

    print("No se encontró una ruta entre los nodos seleccionados.")
    return None

def buscar_ruta_dfs(grafo, inicio_id, meta_id):
  
    # 1. pila para BFS: guarda el (nodo_actual, camino_recorrido)
    stack = [(inicio_id, [inicio_id], 0)]
    
    # 2. Conjunto de visitados para evitar ciclos infinitos
    visitados = {inicio_id}

    while stack:
        (nodo_actual, camino, profundidad) = stack.pop()

        # ¿Llegamos a la meta?
        if nodo_actual == meta_id:
            print("dfs exito")
            return camino

        # Explorar vecinos
        # VALIDACIÓN 3: Verificar que el nodo actual tenga la llave 'vecinos'
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                
                # VALIDACIÓN 4: Solo procesar el vecino si existe en el grafo
                # Esto evita el KeyError si el vecino está fuera del sector (Bounding Box)
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    
                    # Creamos el nuevo camino (forma eficiente de copiar lista)
                    nuevo_camino = camino + [vecino_id]
                    nueva_profundidad = profundidad + 1
                    stack.append((vecino_id, nuevo_camino, nueva_profundidad))

    print("No se encontró una ruta entre los nodos seleccionados.")
    return None


inicio=1524944651
meta= 1441797142

ruta_dfs =buscar_ruta_dfs(grafocompleto,inicio,meta)

ruta_bfs =buscar_ruta_bfs(grafocompleto,inicio,meta)



def visualizar_nodos(nodos_sec, nodos_ruta):
    # Centrar el mapa
    avg_lat = sum(n['lat'] for n in nodos_sec) / len(nodos_sec)
    avg_lon = sum(n['lon'] for n in nodos_sec) / len(nodos_sec)
    mapa = folium.Map(location=[avg_lat, avg_lon], zoom_start=15)
    
    marker_cluster = MarkerCluster().add_to(mapa)
    # Elimina duplicados antes del bucle
    nodos_unicos = {n['id']: n for n in nodos_sec}.values()

    for nodo in nodos_unicos:
        
        if nodo['id'] == nodos_ruta[-1] or nodo['id'] == nodos_ruta[0] :
            folium.CircleMarker(
                location=[nodo['lat'], nodo['lon']],
                # --- PARÁMETROS DE TAMAÑO ---
                radius=10,           # Antes era 3, ahora es 10 (puedes subirlo a 15 o 20)
                weight=5,            # Grosor del borde del círculo
                # ----------------------------
                popup=f"ID: {nodo['id']} indice: {nodos_ruta.index(nodo['id'])}",
                color="darkred",     # Color del borde
                fill=True,
                fill_color="green",    # Color del relleno
                fill_opacity=0.7     # Transparencia del relleno
            ).add_to(mapa)
        elif nodo['id'] in nodos_ruta and  nodo['id'] != nodos_ruta[-1]:
                folium.CircleMarker(
                location=[nodo['lat'], nodo['lon']],
                # --- PARÁMETROS DE TAMAÑO ---
                radius=10,           # Antes era 3, ahora es 10 (puedes subirlo a 15 o 20)
                weight=5,            # Grosor del borde del círculo
                # ----------------------------
                popup=f"ID: {nodo['id']} indice : {nodos_ruta.index(nodo['id'])}",
                color="darkred",     # Color del borde
                fill=True,
                fill_color="red",    # Color del relleno
                fill_opacity=0.7     # Transparencia del relleno
                ).add_to(mapa)    
        
    
    mapa.save("nodos_visibles.html")
    print("Mapa generado con nodos más grandes en 'nodos_visibles.html'")
    
visualizar_nodos(nodos_sector,ruta_dfs)