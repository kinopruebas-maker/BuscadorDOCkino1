import os
import fitz  # PyMuPDF
import requests # Importamos la librería para descargas
from flask import Flask, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

# --- Configuración Inicial ---
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# --- Funciones Auxiliares ---
def archivo_permitido(filename):
    """Verifica si el archivo tiene una extensión permitida (pdf)."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def procesar_pdf_logica(ruta_del_archivo, texto_a_buscar, filename):
    """
    Lógica central para abrir un PDF, buscar texto, resaltar y generar un nuevo archivo.
    """
    doc = None
    new_doc = None
    try:
        doc = fitz.open(ruta_del_archivo)
        paginas_encontradas = []
        total_coincidencias = 0

        # --- PASO 1: Encontrar y resaltar en el documento ---
        for num_pagina, pagina in enumerate(doc):
            instancias = pagina.search_for(texto_a_buscar)
            if instancias:
                total_coincidencias += len(instancias)
                # Guardamos el número de página (ej. 1, 2, 3...) si no está ya en la lista
                if (num_pagina + 1) not in paginas_encontradas:
                    paginas_encontradas.append(num_pagina + 1)
                
                # Resaltamos todas las instancias encontradas en la página
                for inst in instancias:
                    resaltado = pagina.add_highlight_annot(inst)
                    resaltado.set_colors(stroke=(1, 0.5, 0)) # Color naranja
                    resaltado.update()
        
        # --- PASO 2: Crear el nuevo PDF solo con las páginas que tienen coincidencias ---
        if total_coincidencias > 0:
            new_doc = fitz.open() # Creamos un documento PDF nuevo y vacío
            
            # Iteramos sobre los números de página que guardamos
            for num_pagina in paginas_encontradas:
                # Copiamos la página ya resaltada del doc original al nuevo
                # (Restamos 1 porque las listas en Python empiezan en 0)
                new_doc.insert_pdf(doc, from_page=num_pagina - 1, to_page=num_pagina - 1)

            output_filename = f"resaltado_{filename}"
            ruta_procesada = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
            
            # Guardamos el NUEVO documento con las páginas filtradas
            new_doc.save(ruta_procesada, garbage=4, deflate=True, clean=True)
            
            mensaje_exito = (f"Se encontraron {total_coincidencias} coincidencias. "
                             f"Se ha generado un nuevo PDF con las páginas relevantes: {', '.join(map(str, paginas_encontradas))}.")
            
            return render_template('resultado.html', 
                                   mensaje_titulo="¡Proceso Completado!",
                                   mensaje_cuerpo=mensaje_exito,
                                   archivo_descarga=output_filename)
        else:
            return render_template('resultado.html', 
                                   mensaje_titulo="Sin Resultados",
                                   mensaje_cuerpo=f"No se encontró el texto '{texto_a_buscar}' en el documento.")

    except Exception as e:
        return render_template('resultado.html', mensaje_titulo="Error Inesperado", mensaje_cuerpo=f"Ocurrió un error al procesar el PDF: {e}")
    finally:
        # Cerramos los documentos y limpiamos el archivo temporal
        if doc: doc.close()
        if new_doc: new_doc.close()
        if os.path.exists(ruta_del_archivo):
            os.remove(ruta_del_archivo)

# --- Rutas de la Aplicación ---

@app.route('/')
def index():
    """
    Muestra la página principal o procesa un PDF si se proveen los parámetros desde la URL.
    """
    pdf_url = request.args.get('pdf_url')
    search_text = request.args.get('search_text')

    # Si se pasan los parámetros en la URL, se procesa automáticamente
    if pdf_url and search_text:
        try:
            # Descargamos el archivo desde la URL pública
            response = requests.get(pdf_url, stream=True, timeout=30)
            response.raise_for_status() # Lanza un error si la descarga falla (ej. 404)

            filename = secure_filename(pdf_url.split('/')[-1])
            ruta_temporal = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Guardamos el archivo descargado en el servidor temporalmente
            with open(ruta_temporal, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Enviamos el archivo descargado a nuestra lógica de procesamiento
            return procesar_pdf_logica(ruta_temporal, search_text, filename)

        except requests.exceptions.RequestException as e:
            return render_template('resultado.html', mensaje_titulo="Error de Red", mensaje_cuerpo=f"No se pudo descargar el PDF desde la URL: {e}")
        except Exception as e:
            return render_template('resultado.html', mensaje_titulo="Error General", mensaje_cuerpo=f"Ocurrió un error: {e}")

    # Si no hay parámetros, solo muestra la página normal para subir un archivo
    return render_template('index.html')

@app.route('/procesar', methods=['POST'])
def procesar_pdf_formulario():
    """
    Maneja la subida de archivos desde el formulario HTML de la propia aplicación.
    """
    if 'pdf_file' not in request.files:
        return render_template('resultado.html', mensaje_titulo="Error", mensaje_cuerpo="No se encontró el archivo en la solicitud.")
    
    file = request.files['pdf_file']
    texto_a_buscar = request.form['search_text']

    if file.filename == '' or texto_a_buscar == '':
        return render_template('resultado.html', mensaje_titulo="Error", mensaje_cuerpo="Debes seleccionar un archivo y escribir un texto.")

    if file and archivo_permitido(file.filename):
        filename = secure_filename(file.filename)
        ruta_original = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(ruta_original)
        
        # Llama a la misma función de lógica para procesar el archivo subido
        return procesar_pdf_logica(ruta_original, texto_a_buscar, filename)

    return render_template('resultado.html', mensaje_titulo="Error de Archivo", mensaje_cuerpo="El archivo no es un PDF válido.")

@app.route('/download/<filename>')
def download_file(filename):
    """Permite al usuario descargar el archivo PDF ya procesado."""
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    # Esta configuración es para desarrollo. Render usará el comando del Procfile.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
