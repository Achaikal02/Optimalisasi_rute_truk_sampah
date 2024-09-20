import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta  # Updated import

# Mengimpor fungsi dari optimalisasi_rute_truk_sampah.py
from optimalisasi_rute_truk_sampah import create_data_model, calculate_route, filter_locations_by_day, visualize_route, get_route_coordinates

# Fungsi untuk menghasilkan peta animasi Plotly
def generate_animation(locations, route, total_distance):
    """
    Fungsi ini akan menghasilkan animasi pergerakan truk pada peta Plotly berdasarkan lokasi dan rute.
    Memberikan marker dengan warna yang berbeda untuk depot dan tempat sampah.
    """
    latitudes = []
    longitudes = []
    
    # Mendapatkan koordinat rute yang mengikuti jalan dari OSRM
    for i in range(len(route) - 1):
        origin = f"{locations[route[i]][1]},{locations[route[i]][0]}"  
        destination = f"{locations[route[i + 1]][1]},{locations[route[i + 1]][0]}"  
        route_coordinates = get_route_coordinates(origin, destination)
        
        if route_coordinates:
            latitudes.extend([coord[0] for coord in route_coordinates])
            longitudes.extend([coord[1] for coord in route_coordinates])
    
    # Membuat frame untuk setiap langkah rute
    frames = []
    for k in range(len(latitudes)):
        if k == 0:
            # Frame pertama menampilkan depot
            frames.append(go.Frame(
                data=[
                    go.Scattermapbox(
                        lat=latitudes[:k+1],
                        lon=longitudes[:k+1],
                        mode="lines",  # Garis rute
                        line=dict(width=2, color="blue"),
                        hoverinfo="none"
                    ),
                    go.Scattermapbox(
                        lat=[latitudes[0]],  # Marker hanya untuk depot pada frame pertama
                        lon=[longitudes[0]],
                        mode="markers",
                        marker=dict(size=15, color="green"),  # Marker depot di awal
                        hoverinfo="none"
                    )
                ],
                name=f"frame{k}"
            ))
        else:
            # Frame berikutnya hanya menampilkan rute
            frames.append(go.Frame(
                data=[
                    go.Scattermapbox(
                        lat=latitudes[:k+1],
                        lon=longitudes[:k+1],
                        mode="lines",  # Garis rute
                        line=dict(width=2, color="blue"),
                        hoverinfo="none"
                    )
                ],
                name=f"frame{k}"
            ))
    
    # Membuat peta dasar Plotly dengan mapbox
    fig = go.Figure(
        data=[
            go.Scattermapbox(
                lat=[latitudes[0]],
                lon=[longitudes[0]],
                mode="markers",
                marker=dict(size=15, color="green"),  # Depot tetap hijau dan besar
                hoverinfo="none"
            )
        ],
        layout=go.Layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=latitudes[0], lon=longitudes[0]),
                zoom=14,  # Atur zoom
            ),
            autosize=True,  # Sesuaikan ukuran peta secara otomatis
            height=600,  # Atur tinggi peta
            margin=dict(l=0, r=0, t=0, b=0),  # Hapus margin untuk memaksimalkan area peta
            updatemenus=[{
                "buttons": [
                    {
                        "args": [None, {"frame": {"duration": 300, "redraw": True}, "fromcurrent": True}],  # Durasi 300 ms per frame
                        "label": "Play",
                        "method": "animate"
                    },
                    {
                        "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}],
                        "label": "Pause",
                        "method": "animate"
                    }
                ],
                "direction": "left",
                "pad": {"r": 10, "t": 87},
                "showactive": False,
                "type": "buttons",
                "x": 0.1,
                "xanchor": "right",
                "y": 0,
                "yanchor": "top"
            }]
        ),
        frames=frames
    )

    return fig

# Fungsi untuk menghitung jadwal pemberangkatan truk berdasarkan permintaan sampah dan jam pemberangkatan
def calculate_truck_departure_schedule():
    schedule = []
    truck_capacity = 25  # Kapasitas truk
    start_time = datetime.strptime("06:00", "%H:%M")  # Start time (6 AM)
    end_time = datetime.strptime("18:00", "%H:%M")  # End time (6 PM)
    working_hours = (end_time - start_time).seconds // 3600  # Total working hours

    # Loop through each day and calculate the number of truck trips required
    for day in range(7):  # 0: Monday, 6: Sunday
        data = create_data_model(day)
        total_waste = sum(data['demands'])  # Total volume of waste for the day
        trips_needed = (total_waste // truck_capacity) + (1 if total_waste % truck_capacity != 0 else 0)

        # Calculate the interval between trips (e.g., spread trips across the working hours)
        if trips_needed > 0:
            interval_between_trips = working_hours // trips_needed
        else:
            interval_between_trips = 0

        # Calculate departure times for each trip
        departure_times = []
        for trip in range(trips_needed):
            departure_time = start_time + timedelta(hours=trip * interval_between_trips)
            departure_times.append(departure_time.strftime("%H:%M"))

        # Add data for this day to the schedule
        schedule.append({
            'Day': ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'][day],
            'Total Waste': total_waste,
            'Trips Needed': trips_needed,
            'Departure Times': ", ".join(departure_times)  # Join times as a string
        })
    
    return pd.DataFrame(schedule)

# Fungsi untuk menampilkan peta statis setelah animasi
def generate_static_map(locations, route, total_distance):
    visualize_route(locations, route, total_distance)
    return html.Iframe(srcDoc=open('route_map.html', 'r').read(), width='100%', height='600')

# Buat aplikasi Dash
app = dash.Dash(__name__)

# Layout aplikasi
app.layout = html.Div([
    html.H1("Truck Route Monitoring Dashboard", style={'text-align': 'center'}),

    html.Div([
        html.H2("Peta Animasi Rute"),
        dcc.Graph(id='animated-map'),
        html.Button("Switch to Static Map", id='switch-button', n_clicks=0),
        html.Div(id='static-map'),
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
            value=datetime.now().weekday(), 
            clearable=False
        )
    ], style={'width': '35%', 'display': 'inline-block', 'vertical-align': 'top', 'padding': '20px'}),

    html.Div([
        html.H2("Jadwal Pemberangkatan Truk"),
        html.Table(id='truck-schedule-table')
    ], style={'width': '100%', 'padding': '20px'})
])

# Callback untuk memperbarui peta animasi dan grafik
@app.callback(
    [Output('animated-map', 'figure'), Output('load-graph', 'figure')],
    [Input('day-dropdown', 'value')]
)
def update_dashboard(selected_day):
    # Membuat data model dan memfilter lokasi berdasarkan hari yang dipilih
    data = create_data_model(selected_day)
    filtered_data = filter_locations_by_day(data, selected_day)

    # Menghitung rute berdasarkan data yang sudah difilter
    route, total_distance = calculate_route(filtered_data)

    # Menghasilkan animasi pergerakan truk menggunakan Plotly
    animated_map = generate_animation(filtered_data['locations'], route, total_distance)

    # Menyiapkan data untuk grafik muatan dan jadwal
    df = pd.DataFrame({
        'Lokasi': [f'Lokasi {i}' for i in range(len(filtered_data['locations']))],
        'Muatan': filtered_data['demands'],
        'Jadwal': filtered_data['pickup_schedule']
    })

    # Membuat grafik batang menggunakan Plotly
    fig = px.bar(df, x='Lokasi', y='Muatan', color='Jadwal', title="Muatan dan Jadwal Pengambilan")

    return animated_map, fig

# Callback untuk mengganti peta animasi ke peta statis
@app.callback(
    Output('static-map', 'children'),
    Input('switch-button', 'n_clicks'),
    Input('day-dropdown', 'value')
)
def switch_to_static_map(n_clicks, selected_day):
    if n_clicks > 0:
        data = create_data_model(selected_day)
        filtered_data = filter_locations_by_day(data, selected_day)
        route, total_distance = calculate_route(filtered_data)
        return generate_static_map(filtered_data['locations'], route, total_distance)
    return None

# Callback untuk menampilkan tabel jadwal pemberangkatan truk
@app.callback(
    Output('truck-schedule-table', 'children'),
    Input('day-dropdown', 'value')
)
def update_truck_schedule(selected_day):
    # Hitung jadwal pemberangkatan truk
    schedule_df = calculate_truck_departure_schedule()

    # Buat tabel HTML berdasarkan dataframe
    table_header = [
        html.Tr([html.Th("Hari"), html.Th("Total Volume Sampah (m3)"), html.Th("Jumlah Pemberangkatan Truk"), html.Th("Jam Pemberangkatan")])
    ]
    table_rows = [
        html.Tr([html.Td(schedule_df.iloc[i]['Day']),
                 html.Td(schedule_df.iloc[i]['Total Waste']),
                 html.Td(schedule_df.iloc[i]['Trips Needed']),
                 html.Td(schedule_df.iloc[i]['Departure Times'])]) for i in range(len(schedule_df))
    ]

    return table_header + table_rows

# Menjalankan aplikasi
if __name__ == '__main__':
    app.run_server(debug=True)
