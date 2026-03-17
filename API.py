import googlemaps
import folium
from datetime import datetime

# 1. Configuración
gmaps = googlemaps.Client(key=API_KEY)

def generar_ruta_google(origen, destino):
    # 2. Solicitar la ruta a Google Directions API
    # 'optimization=True' es lo que hace que busque la ruta más eficiente
    now = datetime.now()
    direcciones = gmaps.directions(origen, 
                                  destino, 
                                  mode="driving", 
                                  departure_time=now,
                                  optimize_waypoints=True)

    if not direcciones:
        print("No se encontró la ruta.")
        return

    # Extraer puntos para el mapa (polilínea decodificada)
    ruta = direcciones[0]
    puntos_polyline = ruta['overview_polyline']['points']
    
    # 3. Crear el mapa con Folium
    # Usamos las coordenadas del primer paso para centrar el mapa
    start_lat = ruta['legs'][0]['start_location']['lat']
    start_lng = ruta['legs'][0]['start_location']['lng']
    
    mapa = folium.Map(location=[start_lat, start_lng], zoom_start=14)

    # Decodificar y dibujar la línea de la ruta
    # Nota: googlemaps trae una utilidad para decodificar polilíneas
    linea_coordenadas = googlemaps.convert.decode_polyline(puntos_polyline)
    
    # Convertir a formato [lat, lng] para folium
    camino = [[p['lat'], p['lng']] for p in linea_coordenadas]
    
    folium.PolyLine(camino, color="blue", weight=5, opacity=0.8).add_to(mapa)
    
    # Marcadores
    folium.Marker([start_lat, start_lng], popup="Inicio", icon=folium.Icon(color='green')).add_to(mapa)
    end_lat = ruta['legs'][0]['end_location']['lat']
    end_lng = ruta['legs'][0]['end_location']['lng']
    folium.Marker([end_lat, end_lng], popup="Fin", icon=folium.Icon(color='red')).add_to(mapa)

    # Guardar resultado
    mapa.save("ruta_google_maps.html")
    print("Mapa generado: abre 'ruta_google_maps.html' en tu navegador.")

# Ejecución
generar_ruta_google("Catedral de Culiacán", "UAS Facultad de Informática Culiacán")