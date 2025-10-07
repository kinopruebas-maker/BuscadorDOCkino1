import os
import fitz  # PyMuPDF
import json
from flask import Flask, request, Response, jsonify
from werkzeug.utils import secure_filename
import io
import logging

# --- Configuración Inicial ---
# Versión 1.3: Añadido logging detallado para depuración.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'super-secret-key-kino' 

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def archivo_permitido(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/highlight', methods=['POST'])
def highlight_pdf_api():
    app.logger.info("[MARCADOR PYTHON 1] Petición recibida en endpoint /highlight.")
    
    # --- MARCADOR 2: Inspección de la solicitud ---
    try:
        app.logger.info(f"[MARCADOR PYTHON 2] Campos del formulario recibidos (request.form): {request.form.to_dict()}")
        app.logger.info(f"[MARCADOR PYTHON 3] Archivos recibidos (request.files): {request.files.to_dict()}")
    except Exception as e:
        app.logger.error(f"Error al inspeccionar la solicitud: {e}")

    # 1. Validación de la solicitud
    if 'pdf_file' not in request.files:
        app.logger.error("[ERROR PYTHON] No se encontró 'pdf_file' en request.files.")
        return jsonify({ "success": False, "error": "Archivo no encontrado", "details": "La solicitud POST debe incluir una parte 'pdf_file'." }), 400

    file = request.files['pdf_file']
    codes_raw = request.form.get('specific_codes', '')
    
    if file.filename == '':
        app.logger.error("[ERROR PYTHON] El nombre del archivo está vacío.")
        return jsonify({"success": False, "error": "Nombre de archivo vacío"}), 400
    
    if not codes_raw.strip():
        app.logger.error("[ERROR PYTHON] El campo 'specific_codes' está vacío o no presente.")
        return jsonify({ "success": False, "error": "Códigos no proporcionados", "details": "No se encontraron códigos en el campo 'specific_codes' para resaltar." }), 400

    if not file or not archivo_permitido(file.filename):
        app.logger.error(f"[ERROR PYTHON] Archivo no permitido: {file.filename}")
        return jsonify({"success": False, "error": "Tipo de archivo no válido"}), 400

    codigos_a_buscar = list(set(filter(None, codes_raw.splitlines())))
    app.logger.info(f"[MARCADOR PYTHON 4] Se procesarán {len(codigos_a_buscar)} códigos únicos.")
    
    pdf_bytes = file.read()
    
    try:
        app.logger.info("[MARCADOR PYTHON 5] Intentando abrir el PDF con PyMuPDF.")
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        app.logger.info(f"PDF abierto exitosamente. El documento tiene {len(doc)} páginas.")
        
        paginas_encontradas = set()
        total_coincidencias = 0

        for pagina in doc:
            for codigo in codigos_a_buscar:
                instancias = pagina.search_for(codigo)
                if instancias:
                    total_coincidencias += len(instancias)
                    paginas_encontradas.add(pagina.number + 1)
                    for inst in instancias:
                        resaltado = pagina.add_highlight_annot(inst)
                        resaltado.set_colors(stroke=(1, 1, 0))
                        resaltado.update()
        
        app.logger.info(f"[MARCADOR PYTHON 6] Búsqueda finalizada. Total de coincidencias: {total_coincidencias}.")

        if total_coincidencias > 0:
            output_buffer = io.BytesIO()
            doc.save(output_buffer, garbage=4, deflate=True)
            doc.close()
            output_buffer.seek(0)
            response_data = output_buffer.read()
            filename_suffix = f"resaltado_{secure_filename(file.filename)}"
        else:
            doc.close()
            response_data = pdf_bytes
            filename_suffix = f"original_{secure_filename(file.filename)}"

        response = Response(response_data, mimetype='application/pdf')
        pages_list = sorted(list(paginas_encontradas))
        response.headers['X-Pages-Found'] = json.dumps(pages_list)
        response.headers['Content-Disposition'] = f'attachment; filename="{filename_suffix}"'
        
        app.logger.info(f"[MARCADOR PYTHON 7] Enviando respuesta PDF al cliente. Páginas con códigos: {pages_list}")
        return response

    except Exception as e:
        app.logger.error(f"[ERROR CRÍTICO PYTHON] Fallo durante el procesamiento del PDF: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Error al procesar el archivo PDF",
            "details": f"El servicio no pudo leer o modificar el documento. Posiblemente está corrupto o tiene un formato no soportado. Error técnico: {str(e)}"
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)