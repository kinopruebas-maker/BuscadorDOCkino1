import os
import fitz  # PyMuPDF
import requests
from flask import Flask, render_template, request, send_from_directory, flash, redirect, url_for
from werkzeug.utils import secure_filename

# --- Configuración Inicial ---
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
# Se necesita una clave secreta para usar mensajes flash
app.config['SECRET_KEY'] = 'super-secret-key' 

# Asegurarse de que las carpetas de carga y procesados existan
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# --- Funciones Auxiliares ---
def archivo_permitido(filename):
    """Verifica si el archivo tiene una extensión permitida (pdf)."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def procesar_pdf_logica(ruta_del_archivo, texto_a_buscar, filename):
    """
    Lógica central para abrir un PDF, buscar texto, resaltar y generar un nuevo archivo.
    """
    try:
        doc = fitz.open(ruta_del_archivo)
    except fitz.fitz.FileNotFoundError:
        return render_template('resultado.html', mensaje_titulo="Error", mensaje_cuerpo="El archivo no se encontró en la ruta especificada.")
    except Exception as e:
        return render_template('resultado.html', mensaje_titulo="Error al Abrir el PDF", mensaje_cuerpo=f"No se pudo abrir el archivo PDF: {e}")

    paginas_encontradas = []
    total_coincidencias = 0
    new_doc = fitz.open()  # Crear un nuevo documento PDF vacío

    # --- PASO 1: Encontrar y resaltar en el documento ---
    for num_pagina, pagina in enumerate(doc):
        instancias = pagina.search_for(texto_a_buscar)
        if instancias:
            total_coincidencias += len(instancias)
            if (num_pagina + 1) not in paginas_encontradas:
                paginas_encontradas.append(num_pagina + 1)
            
            for inst in instancias:
                resaltado = pagina.add_highlight_annot(inst)
                resaltado.set_colors(stroke=(1, 0.5, 0)) # Color naranja
                resaltado.update()
            
            # Copiar la página resaltada al nuevo documento
            new_doc.insert_pdf(doc, from_page=num_pagina, to_page=num_pagina)

    doc.close() # Cerrar el documento original tan pronto como sea posible

    # --- PASO 2: Guardar el nuevo PDF si se encontraron coincidencias ---
    if total_coincidencias > 0:
        output_filename = f"resaltado_{secure_filename(filename)}"
        ruta_procesada = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        
        try:
            new_doc.save(ruta_procesada, garbage=4, deflate=True, clean=True)
        except Exception as e:
            new_doc.close()
            return render_template('resultado.html', mensaje_titulo="Error al Guardar", mensaje_cuerpo=f"No se pudo guardar el archivo PDF procesado: {e}")
        finally:
            new_doc.close()

        mensaje_exito = (f"Se encontraron {total_coincidencias} coincidencias. "
                         f"Se ha generado un nuevo PDF con las páginas relevantes: {', '.join(map(str, paginas_encontradas))}.")
        
        return render_template('resultado.html', 
                               mensaje_titulo="¡Proceso Completado!",
                               mensaje_cuerpo=mensaje_exito,
                               archivo_descarga=output_filename)
    else:
        new_doc.close()
        return render_template('resultado.html', 
                               mensaje_titulo="Sin Resultados",
                               mensaje_cuerpo=f"No se encontró el texto '{texto_a_buscar}' en el documento.")
    finally:
        # Limpiar el archivo subido original después del procesamiento
        if os.path.exists(ruta_del_archivo):
            os.remove(ruta_del_archivo)


# --- Rutas de la Aplicación ---
@app.route('/')
def index():
    """Muestra la página principal."""
    return render_template('index.html')

@app.route('/procesar-url', methods=['GET'])
def procesar_pdf_url():
    """Procesa un PDF desde una URL."""
    pdf_url = request.args.get('pdf_url')
    search_text = request.args.get('search_text')

    if not pdf_url or not search_text:
        return render_template('resultado.html', mensaje_titulo="Error", mensaje_cuerpo="Faltan parámetros en la URL (pdf_url, search_text).")

    try:
        response = requests.get(pdf_url, stream=True, timeout=30)
        response.raise_for_status()

        filename = secure_filename(pdf_url.split('/')[-1])
        if not archivo_permitido(filename):
            return render_template('resultado.html', mensaje_titulo="Error de Archivo", mensaje_cuerpo="La URL no apunta a un archivo PDF válido.")

        ruta_temporal = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        with open(ruta_temporal, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return procesar_pdf_logica(ruta_temporal, search_text, filename)

    except requests.exceptions.RequestException as e:
        return render_template('resultado.html', mensaje_titulo="Error de Red", mensaje_cuerpo=f"No se pudo descargar el PDF desde la URL: {e}")
    except Exception as e:
        return render_template('resultado.html', mensaje_titulo="Error General", mensaje_cuerpo=f"Ocurrió un error: {e}")

@app.route('/procesar-formulario', methods=['POST'])
def procesar_pdf_formulario():
    """Maneja la subida de archivos desde el formulario HTML."""
    if 'pdf_file' not in request.files:
        flash("No se encontró el archivo en la solicitud.")
        return redirect(url_for('index'))
    
    file = request.files['pdf_file']
    texto_a_buscar = request.form.get('search_text', '').strip()

    if file.filename == '' or texto_a_buscar == '':
        flash("Debes seleccionar un archivo y escribir un texto para buscar.")
        return redirect(url_for('index'))

    if file and archivo_permitido(file.filename):
        filename = secure_filename(file.filename)
        ruta_original = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(ruta_original)
        
        return procesar_pdf_logica(ruta_original, texto_a_buscar, filename)
    else:
        flash("El archivo no es un PDF válido.")
        return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    """Permite al usuario descargar el archivo PDF ya procesado."""
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)