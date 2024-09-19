import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import folium
import pandas as pd
import plotly.express as px
import datetime

# Mengimpor fungsi dari optimalisasi_rute_truk_sampah.py
from optimalisasi_rute_truk_sampah import create_data_model, calculate_route, visualize_route, filter_locations_by_day, get_route_coordinates

# Fungsi untuk menghasilkan peta Folium
def generate_folium_map(locations, route, total_distance):
    """
    Fungsi ini akan menghasilkan peta Folium berdasarkan lokasi, rute, dan total jarak.
    """
    depot_location = locations[0]
    m = folium.Map(location=depot_location, zoom_start=14)

    # Tambahkan marker untuk depot dan setiap tempat sampah
    for i, location in enumerate(locations):
        folium.Marker(location=location, popup=f'Lokasi {i}').add_to(m)

    # Mendapatkan koordinat rute dari OSRM API
    route_coordinates = []
    for i in range(len(route) - 1):
        origin = f"{locations[route[i]][1]},{locations[route[i]][0]}"  # OSRM expects [lng,lat]
        destination = f"{locations[route[i + 1]][1]},{locations[route[i + 1]][0]}"  # OSRM expects [lng,lat]
        temp_coordinates = get_route_coordinates(origin, destination)
        if temp_coordinates:
            route_coordinates.extend(temp_coordinates)

    # Tambahkan rute ke peta jika ada koordinat yang valid
    if route_coordinates:
        folium.PolyLine(route_coordinates, color='blue', weight=2.5, opacity=1).add_to(m)

    # Tambahkan informasi jarak ke peta
    folium.Marker(location=depot_location, 
                  popup=f'Total distance: {total_distance/1000} km',
                  icon=folium.Icon(color='green')).add_to(m)

    return m._repr_html_()  # Mengembalikan HTML peta

# Buat aplikasi Dash
app = dash.Dash(__name__)

# Layout aplikasi
app.layout = html.Div([
    html.H1("Truck Route Monitoring Dashboard", style={'text-align': 'center'}),

    html.Div([
        html.H2("Peta Rute"),
        html.Iframe(id='map', width='100%', height='500'),
    ], style={'width': '60%', 'display': 'inline-block', 'padding': '20px'}),

    html.Div([
        html.H2("Muatan dan Jadwal"),
        dcc.Graph(id='load-graph'),
        html.P("Pilih Hari:"),
        dcc.Dropdown(
            id='day-dropdown',
            options=[
                {'label': 'Senin', 'value': 0},
                {'label': 'Selasa', 'value': 1},
                {'label': 'Rabu', 'value': 2},
                {'label': 'Kamis', 'value': 3},
                {'label': 'Jumat', 'value': 4},
                {'label': 'Sabtu', 'value': 5},
                {'label': 'Minggu', 'value': 6},
            ],
            value=datetime.datetime.now().weekday(),  # Default ke hari ini
            clearable=False
        )
    ], style={'width': '35%', 'display': 'inline-block', 'vertical-align': 'top', 'padding': '20px'})
])

# Callback untuk memperbarui peta dan grafik
@app.callback(
    [Output('map', 'srcDoc'), Output('load-graph', 'figure')],
    [Input('day-dropdown', 'value')]
)
def update_dashboard(selected_day):
    # Membuat data model dan memfilter lokasi berdasarkan hari yang dipilih
    data = create_data_model(selected_day)
    filtered_data = filter_locations_by_day(data, selected_day)

    # Menghitung rute berdasarkan data yang sudah difilter
    route, total_distance = calculate_route(filtered_data)

    # Menghasilkan peta Folium berdasarkan rute yang dihitung
    folium_map = generate_folium_map(filtered_data['locations'], route, total_distance)

    # Menyiapkan data untuk grafik muatan dan jadwal
    df = pd.DataFrame({
        'Lokasi': [f'Lokasi {i}' for i in range(len(filtered_data['locations']))],
        'Muatan': filtered_data['demands'],
        'Jadwal': filtered_data['pickup_schedule']
    })

    # Membuat grafik batang menggunakan Plotly
    fig = px.bar(df, x='Lokasi', y='Muatan', color='Jadwal', title="Muatan dan Jadwal Pengambilan")

    return folium_map, fig

# Menjalankan aplikasi
if __name__ == '__main__':
    app.run_server(debug=True)
