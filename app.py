# app.py
# Versión 2.0: Extracción de páginas con coincidencias.
import os
import fitz  # PyMuPDF
import json
from flask import Flask, request, Response, jsonify
from werkzeug.utils import secure_filename
import io
import logging

# --- Configuración Inicial ---
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
    
    # 1. Validación de la solicitud (sin cambios)
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
        app.logger.info("[MARCADOR PYTHON 5] Abriendo PDF original con PyMuPDF.")
        doc_original = fitz.open(stream=pdf_bytes, filetype="pdf")
        app.logger.info(f"PDF original abierto. El documento tiene {len(doc_original)} páginas.")
        
        paginas_encontradas = set()
        indices_paginas_con_coincidencias = []
        total_coincidencias = 0

        # --- NUEVA LÓGICA: PRIMERO BUSCAR, LUEGO PROCESAR ---
        app.logger.info("[MARCADOR PYTHON 6] Iniciando fase de búsqueda en todo el documento.")
        for i, pagina in enumerate(doc_original):
            pagina_tiene_coincidencia = False
            for codigo in codigos_a_buscar:
                instancias = pagina.search_for(codigo)
                if instancias:
                    total_coincidencias += len(instancias)
                    paginas_encontradas.add(pagina.number + 1)
                    pagina_tiene_coincidencia = True
                    # Resaltar directamente en la página original
                    for inst in instancias:
                        resaltado = pagina.add_highlight_annot(inst)
                        resaltado.set_colors(stroke=(1, 1, 0)) # Amarillo
                        resaltado.update()
            
            if pagina_tiene_coincidencia:
                indices_paginas_con_coincidencias.append(i)

        app.logger.info(f"[MARCADOR PYTHON 7] Búsqueda finalizada. Total de coincidencias: {total_coincidencias}. Páginas con coincidencias: {sorted(list(paginas_encontradas))}")

        output_buffer = io.BytesIO()

        if total_coincidencias > 0:
            app.logger.info("[MARCADOR PYTHON 8] Creando nuevo PDF solo con las páginas resaltadas.")
            # Crear un nuevo documento PDF vacío
            doc_nuevo = fitz.open() 
            
            # Copiar solo las páginas con coincidencias al nuevo documento
            for index in indices_paginas_con_coincidencias:
                doc_nuevo.insert_pdf(doc_original, from_page=index, to_page=index)
            
            # Guardar el nuevo PDF en el buffer
            doc_nuevo.save(output_buffer, garbage=4, deflate=True)
            doc_nuevo.close()
            filename_suffix = f"extracto_{secure_filename(file.filename)}"
        else:
            # Si no hay coincidencias, devolvemos el PDF original para que el usuario pueda revisarlo
            app.logger.info("[MARCADOR PYTHON 8] No se encontraron coincidencias. Se devolverá el PDF original.")
            output_buffer.write(pdf_bytes)
            filename_suffix = f"sin_coincidencias_{secure_filename(file.filename)}"
        
        doc_original.close()
        output_buffer.seek(0)
        response_data = output_buffer.read()

        response = Response(response_data, mimetype='application/pdf')
        pages_list = sorted(list(paginas_encontradas))
        response.headers['X-Pages-Found'] = json.dumps(pages_list)
        response.headers['Content-Disposition'] = f'attachment; filename="{filename_suffix}"'
        
        app.logger.info(f"[MARCADOR PYTHON 9] Enviando respuesta PDF al cliente.")
        return response

    except Exception as e:
        app.logger.error(f"[ERROR CRÍTICO PYTHON] Fallo durante el procesamiento del PDF: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Error al procesar el archivo PDF",
            "details": f"El servicio no pudo leer o modificar el documento. Posiblemente está corrupto. Error técnico: {str(e)}"
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)