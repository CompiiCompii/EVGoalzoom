import os
import gdown
import pandas as pd
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Google Drive File ID and Output Path
subfolder = "xls"
csv_path = os.path.join(subfolder, "data.csv")
file_id = "1IpJAHhuNrMswaDpd_LtaYaas9beNHyt9"  # Your Google Drive file ID

# Global DataFrame and loaded flag
df = None
data_loaded = False


def download_file_from_google_drive(file_id, output_path):
    """Downloads CSV file from Google Drive if not already present."""
    url = f"https://drive.google.com/uc?id={file_id}"
    os.makedirs(subfolder, exist_ok=True)
    print(f"Downloading data file to {output_path}...")
    gdown.download(url, output_path, quiet=False)


def load_data():
    global df, data_loaded
    if data_loaded:
        return

    # Ensure subfolder exists 
    os.makedirs(subfolder, exist_ok=True)

    # Download CSV file if not found
    if not os.path.exists(csv_path):
        download_file_from_google_drive(file_id, csv_path)

    # Load CSV file — only necessary columns
    try:
        df = pd.read_csv(
            csv_path,
            usecols=["Calle", "Municipio", "Casa", "Terreno", "Año", "Latitud", "Longitud"]
        )
        df = df.dropna(subset=['Calle'])

        # Ensure numeric columns are correctly typed
        for col in ['Casa', 'Terreno', 'Año']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        print("Data loaded successfully.")
        data_loaded = True

    except Exception as e:
        raise RuntimeError(f"Error loading CSV file: {e}")


@app.before_request
def ensure_data_loaded():
    if not data_loaded and request.endpoint != 'static':
        load_data()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    global df

    try:
        data = request.get_json()

        casa_value = float(data.get('casa')) if data.get('casa') else None
        terreno_value = float(data.get('terreno')) if data.get('terreno') else None
        año_value = float(data.get('año')) if data.get('año') else None
        municipio_filter = data.get('municipio', '').strip().lower()
        calle_filter = data.get('calle', '').strip().lower()

        casa_min = casa_max = casa_value
        terreno_min = terreno_max = terreno_value
        año_min = año_max = None

        casa_percentage = 0.10
        terreno_percentage = 0.10
        año_offset = 5

        while True:
            filters = []

            if casa_value is not None:
                casa_min = casa_value * (1 - casa_percentage)
                casa_max = casa_value * (1 + casa_percentage)
                filters.append((df['Casa'] >= casa_min) & (df['Casa'] <= casa_max))

            if terreno_value is not None:
                terreno_min = terreno_value * (1 - terreno_percentage)
                terreno_max = terreno_value * (1 + terreno_percentage)
                filters.append((df['Terreno'] >= terreno_min) & (df['Terreno'] <= terreno_max))

            if año_value is not None:
                año_min = año_value - año_offset
                año_max = año_value + año_offset
                filters.append(df['Año'].notna() &
                               (df['Año'] >= año_min) &
                               (df['Año'] <= año_max))

            if municipio_filter:
                filters.append(df['Municipio'].str.contains(municipio_filter, case=False, na=False))

            if calle_filter:
                filters.append(df['Calle'].str.contains(calle_filter, case=False, na=False))

            combined = pd.concat(filters, axis=1).all(axis=1)
            filtered_rows = df[combined].sort_values(by='Casa', ascending=True)

            if len(filtered_rows) >= 15:
                filtered_rows = filtered_rows.head(15)
                break
            elif casa_percentage < 0.5:
                casa_percentage += 0.05
                terreno_percentage += 0.05
                if año_value is not None:
                    año_offset += 1
            else:
                filtered_rows = filtered_rows.head(15)
                break

        results = []
        for _, row in filtered_rows.iterrows():
            results.append({
                'Municipio': row['Municipio'],
                'Calle': str(row['Calle']) if pd.notna(row['Calle']) else "Unknown",
                'Casa': row['Casa'],
                'Terreno': row['Terreno'],
                'Año': int(row['Año']) if pd.notna(row['Año']) else "Unknown",
                'Link': f"https://www.google.com/maps?q={row['Latitud']},{row['Longitud']}"
            })

        return jsonify({'results': results})

    except Exception as e:
        return jsonify({'error': str(e)})


if __name__ == '__main__':
    load_data()
    app.run(debug=True)