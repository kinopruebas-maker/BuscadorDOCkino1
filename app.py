import os
import fitz  # PyMuPDF
import json
from flask import Flask, request, send_file, Response, jsonify
from werkzeug.utils import secure_filename
import io

# --- Configuración Inicial ---
# Versión 1.1: Refactorización de manejo de errores y endpoint de API.
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'super-secret-key-kino' 

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Funciones Auxiliares ---
def archivo_permitido(filename):
    """Verifica si el archivo tiene una extensión permitida (pdf)."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Lógica de la API ---
@app.route('/highlight', methods=['POST'])
def highlight_pdf_api():
    """
    Endpoint de API para recibir un PDF y una lista de códigos,
    y devolver el PDF con los códigos resaltados.
    """
    # 1. Validación de la solicitud
    if 'pdf_file' not in request.files:
        return jsonify({
            "success": False, 
            "error": "Archivo no encontrado", 
            "details": "La solicitud POST debe incluir una parte 'pdf_file'."
        }), 400

    file = request.files['pdf_file']
    # El campo se llama 'specific_codes' en la llamada cURL de PHP
    codes_raw = request.form.get('specific_codes', '')
    
    if file.filename == '':
        return jsonify({"success": False, "error": "Nombre de archivo vacío"}), 400
    
    if not codes_raw.strip():
        return jsonify({
            "success": False, 
            "error": "Códigos no proporcionados",
            "details": "No se encontraron códigos en el campo 'specific_codes' para resaltar."
        }), 400

    if not file or not archivo_permitido(file.filename):
        return jsonify({"success": False, "error": "Tipo de archivo no válido"}), 400

    # Lista de códigos únicos y limpios
    codigos_a_buscar = list(set(filter(None, codes_raw.splitlines())))

    try:
        pdf_bytes = file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Error al leer el PDF",
            "details": f"No se pudo procesar el archivo PDF proporcionado. Detalles: {str(e)}"
        }), 500

    paginas_encontradas = set()
    total_coincidencias = 0

    # 2. Búsqueda y resaltado
    for pagina in doc:
        for codigo in codigos_a_buscar:
            instancias = pagina.search_for(codigo)
            if instancias:
                total_coincidencias += len(instancias)
                paginas_encontradas.add(pagina.number + 1)
                for inst in instancias:
                    resaltado = pagina.add_highlight_annot(inst)
                    resaltado.set_colors(stroke=(1, 1, 0)) # Amarillo brillante
                    resaltado.update()
    
    # 3. Generación de la respuesta
    if total_coincidencias > 0:
        try:
            # Guardar el PDF modificado en un buffer de memoria
            output_buffer = io.BytesIO()
            doc.save(output_buffer, garbage=4, deflate=True)
            doc.close()
            output_buffer.seek(0)
            
            # Crear la respuesta con el PDF
            response = Response(output_buffer.read(), mimetype='application/pdf')
            
            # Añadir cabecera con las páginas encontradas
            pages_list = sorted(list(paginas_encontradas))
            response.headers['X-Pages-Found'] = json.dumps(pages_list)
            response.headers['Content-Disposition'] = f'attachment; filename="resaltado_{secure_filename(file.filename)}"'
            
            return response
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Error al guardar el PDF procesado",
                "details": str(e)
            }), 500
    else:
        # Si no se encuentra nada, se devuelve el PDF original sin cambios
        # pero con la información de que no se encontraron códigos.
        doc.close()
        response = Response(pdf_bytes, mimetype='application/pdf')
        response.headers['X-Pages-Found'] = json.dumps([])
        response.headers['Content-Disposition'] = f'attachment; filename="original_{secure_filename(file.filename)}"'
        return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)