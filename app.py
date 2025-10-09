# app.py
# Versión 4.0: Recibe archivo vía HTTP POST (multipart/form-data) y extrae páginas.
import os
import fitz  # PyMuPDF
import json
from flask import Flask, request, Response, jsonify
from werkzeug.utils import secure_filename
import io
import logging

# --- Configuración Inicial ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-kino' 

def archivo_permitido(filename):
    """Verifica si el archivo tiene una extensión permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

@app.route('/highlight', methods=['POST'])
def highlight_pdf_api():
    logging.info("[PYTHON] Petición de resaltado recibida.")
    
    if 'pdf_file' not in request.files:
        logging.error("[PYTHON ERROR] La clave 'pdf_file' no se encontró en los archivos de la solicitud.")
        return jsonify({ "success": False, "error": "Archivo no encontrado", "details": "La solicitud POST debe incluir una parte 'pdf_file'." }), 400

    file = request.files['pdf_file']
    codes_raw = request.form.get('specific_codes', '')
    
    if file.filename == '':
        logging.error("[PYTHON ERROR] El nombre del archivo está vacío.")
        return jsonify({"success": False, "error": "Nombre de archivo vacío"}), 400
    
    if not codes_raw or not codes_raw.strip():
        logging.error("[PYTHON ERROR] El campo 'specific_codes' está vacío o no fue proporcionado.")
        return jsonify({ "success": False, "error": "Códigos no proporcionados", "details": "El campo 'specific_codes' es obligatorio." }), 400

    if not file or not archivo_permitido(file.filename):
        logging.error(f"[PYTHON ERROR] Archivo no permitido o inválido: {file.filename}")
        return jsonify({"success": False, "error": "Tipo de archivo no válido, solo se aceptan PDFs."}), 400

    codigos_a_buscar = list(set(filter(None, codes_raw.splitlines())))
    logging.info(f"[PYTHON] Procesando archivo '{file.filename}' con {len(codigos_a_buscar)} códigos únicos.")
    
    pdf_bytes = file.read()
    
    try:
        doc_original = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        paginas_encontradas = set()
        indices_paginas_con_coincidencias = []
        total_coincidencias = 0

        for i, pagina in enumerate(doc_original):
            pagina_tiene_coincidencia = False
            for codigo in codigos_a_buscar:
                instancias = pagina.search_for(str(codigo))
                if instancias:
                    total_coincidencias += len(instancias)
                    paginas_encontradas.add(pagina.number + 1)
                    pagina_tiene_coincidencia = True
                    for inst in instancias:
                        resaltado = pagina.add_highlight_annot(inst)
                        resaltado.set_colors(stroke=(1, 1, 0)) # Amarillo
                        resaltado.update()
        
            if pagina_tiene_coincidencia:
                indices_paginas_con_coincidencias.append(i)

        logging.info(f"[PYTHON] Búsqueda finalizada. Total de coincidencias: {total_coincidencias}.")

        output_buffer = io.BytesIO()

        if total_coincidencias > 0:
            doc_nuevo = fitz.open()
            for index in indices_paginas_con_coincidencias:
                doc_nuevo.insert_pdf(doc_original, from_page=index, to_page=index)
            doc_nuevo.save(output_buffer, garbage=4, deflate=True)
            doc_nuevo.close()
        else:
            doc_original.save(output_buffer)

        doc_original.close()
        output_buffer.seek(0)
        
        response = Response(output_buffer.read(), mimetype='application/pdf')
        response.headers['X-Pages-Found'] = json.dumps(sorted(list(paginas_encontradas)))
        response.headers['Content-Disposition'] = f'attachment; filename="resaltado_{secure_filename(file.filename)}"'
        
        logging.info("[PYTHON] Enviando respuesta PDF al cliente.")
        return response

    except Exception as e:
        logging.error(f"[PYTHON CRITICAL ERROR] Fallo durante el procesamiento del PDF: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Error interno al procesar el archivo PDF", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)