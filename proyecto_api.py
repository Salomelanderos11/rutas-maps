#%%
import requests
import math
from ipyleaflet import Map, Marker, FullScreenControl, LayerGroup, Polyline
import ipywidgets as widgets
from IPython.display import display
import heapq
from collections import deque  
import random

# coordenadas del sector de culiacan que vamos a usar
sur = 24.796998
oeste = -107.401461
norte = 24.812974
este = -107.387524

# hace la peticion a overpass api y regresa los elementos del sector
def extraer_nodos_sector(south, west, north, east):
    url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:60];
    (way["highway"~"primary|secondary|tertiary|residential"]({south},{west},{north},{east}););
    out body; >; out skel qt;
    """
    r = requests.post(url, data={'data': query})
    if r.status_code == 200:
        return r.json().get('elements', [])
    return []

data = extraer_nodos_sector(sur, oeste, norte, este)

# diccionario con id del nodo como llave y sus coordenadas como valor
nodos_coords = {e['id']: (e['lat'], e['lon']) for e in data if e['type'] == 'node'}

# formula de haversine para calcular distancia real en metros entre dos coordenadas
def calcular_distancia(p1, p2):
    lat1, lon1 = p1
    lat2, lon2 = p2
    radio_tierra = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return radio_tierra * c

# recorre todos los nodos y regresa el id del mas cercano 
def obtener_id_mas_cercano(lat_clic, lon_clic, nodos_dict):
    distancia_minima = float('inf')
    id_mas_cercano = None
    for nodo_id, coords in nodos_dict.items():
        dist = calcular_distancia((lat_clic, lon_clic), coords)
        if dist < distancia_minima:
            distancia_minima = dist
            id_mas_cercano = nodo_id
    return id_mas_cercano, distancia_minima

# construye el grafo con nodos y aristas a partir de los nodos 
# cada nodo tiene lat lon y lista de vecinos con su distancia
def construir_grafo(data):
    grafo = {}
    nodos_c = {e['id']: (e['lat'], e['lon']) for e in data if e['type'] == 'node'}
    for ele in data:
        if ele['type'] == 'way':
            nodos_en_calle = ele.get('nodes', [])
            # conecta cada par de nodos consecutivos en la calle
            for i in range(len(nodos_en_calle) - 1):
                u = nodos_en_calle[i]
                v = nodos_en_calle[i+1]
                if u in nodos_c and v in nodos_c:
                    dist = calcular_distancia(nodos_c[u], nodos_c[v])
                    if u not in grafo:
                        grafo[u] = {'lat': nodos_c[u][0], 'lon': nodos_c[u][1], 'vecinos': []}
                    if v not in grafo:
                        grafo[v] = {'lat': nodos_c[v][0], 'lon': nodos_c[v][1], 'vecinos': []}
                    # conexion en ambas direcciones
                    grafo[u]['vecinos'].append({'id': v, 'peso': dist})
                    grafo[v]['vecinos'].append({'id': u, 'peso': dist})
    return grafo

grafocompleto = construir_grafo(data)

# distancia en metros entre un nodo y la meta usada como heuristica
def heuristica(grafo, nodo_id, meta_id):
    lat_actual = grafo[nodo_id]['lat']
    lon_actual = grafo[nodo_id]['lon']
    lat_meta   = grafo[meta_id]['lat']
    lon_meta   = grafo[meta_id]['lon']
    return calcular_distancia((lat_actual, lon_actual), (lat_meta, lon_meta))

# busqueda por amplitud - explora nivel por nivel garantiza el camino con menos nodos
def buscar_ruta_bfs(grafo, inicio_id, meta_id):
    cola = deque([(inicio_id, [inicio_id])])
    visitados = {inicio_id}
    paso = 0
    while cola:
        nodo_actual, camino = cola.popleft()
        paso = paso + 1
        print("paso " + str(paso) + " - visitando nodo " + str(nodo_actual) + " | nodos en camino: " + str(len(camino)))

        if nodo_actual == meta_id:
            print("BFS exito, nodos: " + str(len(camino)))
            return camino
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    nuevo_camino = camino + [vecino_id]
                    cola.append((vecino_id, nuevo_camino))
    print("BFS: No se encontro ruta.")
    return None

# busqueda por profundidad - usa pila en vez de cola por eso va mas profundo antes de explorar
def buscar_ruta_dfs(grafo, inicio_id, meta_id):
    stack = [(inicio_id, [inicio_id], 0)]
    visitados = {inicio_id}
    paso = 0
    while stack:
        nodo_actual, camino, profundidad = stack.pop()
        paso = paso + 1
        print("paso " + str(paso) + " - visitando nodo " + str(nodo_actual) + " | profundidad: " + str(profundidad) + " | nodos en camino: " + str(len(camino)))

        if nodo_actual == meta_id:
            print("DFS exito, nodos: " + str(len(camino)))
            return camino
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    nuevo_camino = camino + [vecino_id]
                    nueva_profundidad = profundidad + 1
                    stack.append((vecino_id, nuevo_camino, nueva_profundidad))
    print("DFS: No se encontro ruta.")
    return None

# dfs con limite de profundidad - igual que dfs pero para de explorar si llega al limite
def buscar_ruta_ldfs(grafo, inicio_id, meta_id, limite_profundidad=50):
    stack = [(inicio_id, [inicio_id], 0)]
    visitados = {inicio_id}
    paso = 0
    while stack:
        nodo_actual, camino, profundidad = stack.pop()
        paso = paso + 1
        print("paso " + str(paso) + " - visitando nodo " + str(nodo_actual) + " | profundidad: " + str(profundidad) + "/" + str(limite_profundidad))

        if nodo_actual == meta_id:
            print("LDFS exito, nodos: " + str(len(camino)) + ", profundidad: " + str(profundidad))
            return camino
        # si llego al limite no expande este nodo
        if profundidad >= limite_profundidad:
            print("paso " + str(paso) + " - limite alcanzado en nodo " + str(nodo_actual) + " no se expande")
            continue
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    nuevo_camino = camino + [vecino_id]
                    stack.append((vecino_id, nuevo_camino, profundidad + 1))
    print("LDFS: No se encontro ruta con limite " + str(limite_profundidad))
    return None

# busqueda voraz - siempre elige el vecino mas cercano a la meta segun la heuristica
def buscar_ruta_voraz(grafo, inicio_id, meta_id):
    stack = [(inicio_id, [inicio_id])]
    visitados = {inicio_id}
    paso = 0
    while stack:
        nodo_actual, camino = stack.pop()
        paso = paso + 1
        h = heuristica(grafo, nodo_actual, meta_id)
        print("paso " + str(paso) + " - visitando nodo " + str(nodo_actual) + " | distancia a meta: " + str(round(h, 1)) + "m")

        if nodo_actual == meta_id:
            print("Voraz exito, nodos: " + str(len(camino)))
            return camino
        if 'vecinos' in grafo[nodo_actual]:
            candidatos = []
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo and vecino_id not in visitados:
                    visitados.add(vecino_id)
                    h = heuristica(grafo, vecino_id, meta_id)
                    candidatos.append((vecino_id, camino + [vecino_id], h))
            # ordena descendente porque stack.pop() saca el ultimo
            # entonces el mejor queda hasta el final de la lista
            candidatos.sort(key=lambda x: x[2], reverse=True)
            for vecino_id, nuevo_camino, h in candidatos:
                stack.append((vecino_id, nuevo_camino))
    print("Voraz: No se encontro ruta.")
    return None

# a estrella - combina costo real del camino con la heuristica para encontrar la ruta optima
def buscar_ruta_a_star(grafo, inicio_id, meta_id):
    # f = g + h donde g es distancia recorrida y h es distancia estimada a la meta
    open_set = [(heuristica(grafo, inicio_id, meta_id), 0, inicio_id, [inicio_id])]
    mejor_g = {inicio_id: 0}
    nodos_explorados = 0
    while open_set:
        f_score, g_score, nodo_actual, camino = heapq.heappop(open_set)
        nodos_explorados = nodos_explorados + 1
        print("paso " + str(nodos_explorados) + " - visitando nodo " + str(nodo_actual) + " | g: " + str(round(g_score, 1)) + "m | f: " + str(round(f_score, 1)) + "m")

        if nodo_actual == meta_id:
            print("A* exito, nodos: " + str(len(camino)) + ", explorados: " + str(nodos_explorados) + ", distancia: " + str(round(g_score, 1)) + "m")
            return camino
        # si ya encontramos un camino mejor a este nodo lo ignoramos
        if g_score > mejor_g.get(nodo_actual, float('inf')):
            print("  nodo " + str(nodo_actual) + " ignorado porque ya existe un camino mejor")
            continue
        if 'vecinos' in grafo[nodo_actual]:
            for vecino_info in grafo[nodo_actual]['vecinos']:
                vecino_id = vecino_info['id']
                peso = vecino_info['peso']
                if vecino_id not in grafo:
                    continue
                nuevo_g = g_score + peso
                # solo agrega al open set si encontramos un camino mas corto
                if nuevo_g < mejor_g.get(vecino_id, float('inf')):
                    mejor_g[vecino_id] = nuevo_g
                    nuevo_f = nuevo_g + heuristica(grafo, vecino_id, meta_id)
                    nuevo_camino = camino + [vecino_id]
                    heapq.heappush(open_set, (nuevo_f, nuevo_g, vecino_id, nuevo_camino))
                    print("  agregando vecino " + str(vecino_id) + " con f: " + str(round(nuevo_f, 1)) + "m")
    print("A*: No se encontro ruta. Explorados: " + str(nodos_explorados))
    return None

# busqueda tabu - como voraz pero recuerda los ultimos nodos visitados para no repetirlos
def buscar_ruta_tabu(grafo, inicio_id, meta_id, tabu_size=20, max_iteraciones=10000):
    current = inicio_id
    camino = [inicio_id]
    tabu_list = deque()  # guarda el orden de entrada para saber cual es el mas antiguo
    tabu_set = set()     # set para buscar rapido si un nodo esta en la lista tabu
    iteraciones = 0
    while current != meta_id:
        if iteraciones >= max_iteraciones:
            print("Tabu: Limite de iteraciones alcanzado " + str(max_iteraciones))
            return None
        iteraciones = iteraciones + 1
        h = heuristica(grafo, current, meta_id)
        print("iteracion " + str(iteraciones) + " - nodo actual " + str(current) + " | distancia a meta: " + str(round(h, 1)) + "m | tabu size: " + str(len(tabu_list)))

        # solo considera vecinos que no esten en la lista tabu
        candidatos = []
        if 'vecinos' in grafo[current]:
            for vecino_info in grafo[current]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo and vecino_id not in tabu_set:
                    h = heuristica(grafo, vecino_id, meta_id)
                    candidatos.append((vecino_id, h))
        if not candidatos:
            print("Tabu: Sin movimientos disponibles en iteracion " + str(iteraciones))
            return None
        # elige el mejor candidato segun la heuristica
        candidatos.sort(key=lambda x: x[1])
        siguiente_id = candidatos[0][0]
        print("  moviendose a nodo " + str(siguiente_id) + " | candidatos disponibles: " + str(len(candidatos)))

        # agrega el nodo actual a tabu antes de moverse
        tabu_list.append(current)
        tabu_set.add(current)
        # elimina el nodo mas antiguo si se paso del limite
        if len(tabu_list) > tabu_size:
            nodo_viejo = tabu_list.popleft()
            tabu_set.discard(nodo_viejo)
            print("  nodo " + str(nodo_viejo) + " eliminado de la lista tabu")
        current = siguiente_id
        camino.append(current)
    print("Tabu exito, nodos: " + str(len(camino)) + ", iteraciones: " + str(iteraciones))
    return camino

# recocido simulado - como voraz pero acepta movimientos malos con cierta probabilidad
# la probabilidad de aceptar un mal movimiento baja conforme la temperatura disminuye
def buscar_ruta_recocido(grafo, inicio_id, meta_id, temp_inicial=1000, tasa_enfriamiento=0.995, max_iteraciones=10000):
    current = inicio_id
    camino = [inicio_id]
    temp = temp_inicial
    iteraciones = 0
    while current != meta_id and temp > 0.1:
        if iteraciones >= max_iteraciones:
            print("Recocido: Limite de iteraciones alcanzado " + str(max_iteraciones))
            return None
        iteraciones = iteraciones + 1
        print("iteracion " + str(iteraciones) + " - nodo actual " + str(current) + " | temperatura: " + str(round(temp, 2)))

        candidatos = []
        if 'vecinos' in grafo[current]:
            for vecino_info in grafo[current]['vecinos']:
                vecino_id = vecino_info['id']
                if vecino_id in grafo:
                    h = heuristica(grafo, vecino_id, meta_id)
                    candidatos.append((vecino_id, h))
        if not candidatos:
            print("Recocido: Sin movimientos disponibles.")
            return None
        candidatos.sort(key=lambda x: x[1])
        siguiente_id = candidatos[0][0]
        h_siguiente = candidatos[0][1]
        h_actual = heuristica(grafo, current, meta_id)
        # delta positivo significa que el movimiento nos aleja de la meta
        delta = h_siguiente - h_actual
        # acepta el movimiento si mejora o con probabilidad e^(-delta/temp)
        if delta < 0 or random.random() < math.exp(-delta / temp):
            print("  movimiento aceptado hacia nodo " + str(siguiente_id) + " | delta: " + str(round(delta, 1)))
            current = siguiente_id
            camino.append(current)
        else:
            print("  movimiento rechazado hacia nodo " + str(siguiente_id) + " | delta: " + str(round(delta, 1)))
        # enfria la temperatura en cada iteracion
        temp = temp * tasa_enfriamiento
    if current == meta_id:
        print("Recocido exito, nodos: " + str(len(camino)) + ", iteraciones: " + str(iteraciones))
        return camino
    print("Recocido: Temperatura agotada, no se llego a la meta.")
    return None

# mapa centrado en el sector
m = Map(center=(24.805, -107.394), zoom=15)
m.add_control(FullScreenControl())

capa_interactiva = LayerGroup()
capa_ruta = LayerGroup()
m.add_layer(capa_interactiva)
m.add_layer(capa_ruta)

# guarda los puntos que el usuario va seleccionando
puntos_seleccionados = []
nodos_id_ruta = {"inicio": None, "meta": None}
out = widgets.Output()
ejecutando = False

# dibuja el camino en el mapa como una linea azul
def dibujar_ruta(camino):
    if camino != None:
        print("Camino (IDs): " + str(camino))
        coords = []
        for nid in camino:
            if nid in grafocompleto:
                lat = grafocompleto[nid]['lat']
                lon = grafocompleto[nid]['lon']
                coords.append([lat, lon])
        capa_ruta.clear_layers()
        linea = Polyline(locations=coords, color="blue", weight=4, opacity=0.8)
        capa_ruta.add_layer(linea)
    else:
        print("No se encontro ruta.")

# verifica que el usuario haya seleccionado dos puntos validos antes de buscar
def validar_puntos():
    if nodos_id_ruta["inicio"] == None or nodos_id_ruta["meta"] == None:
        print("Selecciona dos puntos en el mapa primero.")
        return None, None
    inicio = nodos_id_ruta["inicio"]
    meta = nodos_id_ruta["meta"]
    if inicio not in grafocompleto:
        print("El nodo de inicio no esta en el grafo.")
        return None, None
    if meta not in grafocompleto:
        print("El nodo meta no esta en el grafo.")
        return None, None
    return inicio, meta

# ejecuta bfs cuando el usuario presiona el boton
def on_bfs(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando BFS...")
            camino = buscar_ruta_bfs(grafocompleto, inicio, meta)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta dfs cuando el usuario presiona el boton
def on_dfs(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando DFS...")
            camino = buscar_ruta_dfs(grafocompleto, inicio, meta)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta ldfs cuando el usuario presiona el boton
def on_ldfs(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando LDFS...")
            camino = buscar_ruta_ldfs(grafocompleto, inicio, meta, limite_profundidad=50)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta voraz cuando el usuario presiona el boton
def on_voraz(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando Voraz...")
            camino = buscar_ruta_voraz(grafocompleto, inicio, meta)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta a star cuando el usuario presiona el boton
def on_astar(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando A*...")
            camino = buscar_ruta_a_star(grafocompleto, inicio, meta)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta tabu cuando el usuario presiona el boton
def on_tabu(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando Tabu...")
            camino = buscar_ruta_tabu(grafocompleto, inicio, meta, tabu_size=20, max_iteraciones=10000)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# ejecuta recocido simulado cuando el usuario presiona el boton
def on_recocido(b):
    global ejecutando
    if ejecutando == True:
        return
    ejecutando = True
    with out:
        try:
            inicio, meta = validar_puntos()
            if inicio == None:
                ejecutando = False
                return
            print("Ejecutando Recocido Simulado...")
            camino = buscar_ruta_recocido(grafocompleto, inicio, meta, temp_inicial=1000, tasa_enfriamiento=0.995)
            dibujar_ruta(camino)
        except Exception as e:
            print("ERROR: " + str(e))
        ejecutando = False

# limpia el mapa y reinicia los puntos seleccionados
def limpiar(b):
    puntos_seleccionados.clear()
    capa_interactiva.clear_layers()
    capa_ruta.clear_layers()
    nodos_id_ruta["inicio"] = None
    nodos_id_ruta["meta"] = None
    out.clear_output(wait=True)
    with out:
        print("Mapa limpio.")

# captura el clic del usuario en el mapa y guarda el nodo mas cercano
def manejar_clic(**kwargs):
    if kwargs.get('type') == 'click':
        latlon = kwargs.get('coordinates')
        if len(puntos_seleccionados) < 2:
            puntos_seleccionados.append(latlon)
            nodo_id, distancia = obtener_id_mas_cercano(latlon[0], latlon[1], nodos_coords)
            if len(puntos_seleccionados) == 1:
                tipo = "INICIO"
                nodos_id_ruta["inicio"] = nodo_id
            else:
                tipo = "META"
                nodos_id_ruta["meta"] = nodo_id
            marcador = Marker(location=latlon, draggable=False, title=tipo + ": " + str(nodo_id))
            capa_interactiva.add_layer(marcador)
            print(tipo + " capturado. ID Nodo OSM: " + str(nodo_id))
            if len(puntos_seleccionados) == 2:
                print("LISTO - Origen: " + str(nodos_id_ruta['inicio']) + " | Destino: " + str(nodos_id_ruta['meta']))

# remove=True evita que se acumulen listeners si se re-ejecuta la celda
m.on_interaction(manejar_clic, remove=True)
m.on_interaction(manejar_clic)

# %%
# botones
out.clear_output()

btn_bfs      = widgets.Button(description="BFS",      button_style='primary')
btn_dfs      = widgets.Button(description="DFS",      button_style='primary')
btn_ldfs     = widgets.Button(description="LDFS",     button_style='primary')
btn_voraz    = widgets.Button(description="Voraz",    button_style='info')
btn_astar    = widgets.Button(description="A*",       button_style='info')
btn_tabu     = widgets.Button(description="Tabu",     button_style='warning')
btn_recocido = widgets.Button(description="Recocido", button_style='warning')
btn_reset    = widgets.Button(description="Limpiar",  button_style='danger')

btn_bfs.on_click(on_bfs)
btn_dfs.on_click(on_dfs)
btn_ldfs.on_click(on_ldfs)
btn_voraz.on_click(on_voraz)
btn_astar.on_click(on_astar)
btn_tabu.on_click(on_tabu)
btn_recocido.on_click(on_recocido)
btn_reset.on_click(limpiar)

display(m)
display(widgets.HBox([btn_bfs, btn_dfs, btn_ldfs, btn_voraz]))
display(widgets.HBox([btn_astar, btn_tabu, btn_recocido, btn_reset]))
display(out)
# %%