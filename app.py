import os
import fitz  # PyMuPDF
from flask import Flask, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

def archivo_permitido(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/procesar', methods=['POST'])
def procesar_pdf():
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

        try:
            doc = fitz.open(ruta_original)
            paginas_encontradas = []
            total_coincidencias = 0

            for num_pagina, pagina in enumerate(doc):
                instancias = pagina.search_for(texto_a_buscar)
                if instancias:
                    total_coincidencias += len(instancias)
                    if (num_pagina + 1) not in paginas_encontradas:
                        paginas_encontradas.append(num_pagina + 1)

                    for inst in instancias:
                        resaltado = pagina.add_highlight_annot(inst)
                        resaltado.set_colors(stroke=(1, 0.5, 0))
                        resaltado.update()

            if total_coincidencias > 0:
                output_filename = f"resaltado_{filename}"
                ruta_procesada = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
                doc.save(ruta_procesada, garbage=4, deflate=True, clean=True)

                mensaje_exito = (f"Se encontraron {total_coincidencias} coincidencias en las páginas: "
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
            if 'doc' in locals():
                doc.close()
            if os.path.exists(ruta_original):
                os.remove(ruta_original)

    return render_template('resultado.html', mensaje_titulo="Error", mensaje_cuerpo="El archivo no es un PDF válido.")

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))