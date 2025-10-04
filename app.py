import os
import fitz  # PyMuPDF
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

# --- Rutas de la Aplicación ---

@app.route('/')
def index():
    """Muestra la página principal con el formulario de carga."""
    return render_template('index.html')

@app.route('/procesar', methods=['POST'])
def procesar_pdf():
    """
    Recibe el archivo y el texto, procesa el PDF y muestra la página de resultados.
    """
    if 'pdf_file' not in request.files:
        return render_template('resultado.html', mensaje_titulo="Error", mensaje_cuerpo="No se encontró el archivo en la solicitud.")
    
    file = request.files['pdf_file']
    texto_a_buscar = request.form['search_text']

    if file.filename == '' or texto_a_buscar == '':
        return render_template('resultado.html', mensaje_titulo="Error", mensaje_cuerpo="Debes seleccionar un archivo y escribir un texto para buscar.")

    if file and archivo_permitido(file.filename):
        filename = secure_filename(file.filename)
        ruta_original = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(ruta_original)

        doc = None
        new_doc = None
        try:
            doc = fitz.open(ruta_original)
            paginas_encontradas = []
            total_coincidencias = 0

            # --- PASO 1: Encontrar y resaltar en el documento original (en memoria) ---
            for num_pagina, pagina in enumerate(doc):
                instancias = pagina.search_for(texto_a_buscar)
                if instancias:
                    total_coincidencias += len(instancias)
                    # Guardamos el número de página (ej. 1, 2, 3...)
                    if (num_pagina + 1) not in paginas_encontradas:
                        paginas_encontradas.append(num_pagina + 1)
                    
                    for inst in instancias:
                        resaltado = pagina.add_highlight_annot(inst)
                        resaltado.set_colors(stroke=(1, 0.5, 0)) # Color naranja
                        resaltado.update()
            
            # --- PASO 2: Crear el nuevo PDF solo con las páginas encontradas ---
            if total_coincidencias > 0:
                # Creamos un documento PDF nuevo y vacío
                new_doc = fitz.open() 
                
                # Iteramos sobre los números de página que encontramos (ej. 5, 8, 12)
                for num_pagina in paginas_encontradas:
                    # Copiamos la página ya resaltada del doc original al nuevo
                    # (Restamos 1 porque las listas empiezan en 0)
                    new_doc.insert_pdf(doc, from_page=num_pagina - 1, to_page=num_pagina - 1)

                output_filename = f"filtrado_{filename}"
                ruta_procesada = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
                
                # Guardamos el NUEVO documento, no el original
                new_doc.save(ruta_procesada, garbage=4, deflate=True, clean=True)
                
                mensaje_exito = (f"Se encontraron {total_coincidencias} coincidencias. "
                                 f"Se ha generado un nuevo PDF solo con las páginas relevantes: "
                                 f"{', '.join(map(str, paginas_encontradas))}.")
                
                return render_template('resultado.html', 
                                       mensaje_titulo="¡Proceso Completado!",
                                       mensaje_cuerpo=mensaje_exito,
                                       archivo_descarga=output_filename)
            else:
                return render_template('resultado.html', 
                                       mensaje_titulo="Sin Resultados",
                                       mensaje_cuerpo=f"No se encontró el texto '{texto_a_buscar}' en el documento.")

        except Exception as e:
            return render_template('resultado.html', mensaje_titulo="Error", mensaje_cuerpo=f"Ocurrió un error al procesar el PDF: {e}")
        finally:
            # Nos aseguramos de cerrar ambos documentos si fueron abiertos
            if doc:
                doc.close()
            if new_doc:
                new_doc.close()
            # Limpiar el archivo subido
            if os.path.exists(ruta_original):
                 os.remove(ruta_original)

    return render_template('resultado.html', mensaje_titulo="Error", mensaje_cuerpo="El archivo no es un PDF válido.")

@app.route('/download/<filename>')
def download_file(filename):
    """Permite al usuario descargar el archivo procesado."""
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))