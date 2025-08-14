import os
import base64
import logging
from io import BytesIO
from PIL import Image, UnidentifiedImageError, ImageFile
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from flask import Flask, request, redirect, url_for, render_template_string, flash, jsonify
from werkzeug.exceptions import RequestEntityTooLarge
from flask_cors import CORS  # pip install flask-cors

# --- Configurações de segurança e limites ---
Image.MAX_IMAGE_PIXELS = 25_000_000
ImageFile.LOAD_TRUNCATED_IMAGES = True

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

# --- Criação da aplicação ---
app = Flask(__name__, static_folder="static")

# Limite de upload
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Ativar CORS (ajuste origins para o seu GitHub Pages se quiser restringir)
CORS(app, resources={r"/*": {"origins": [
    "https://gustavojung.github.io/",
    "https://gustavojung.github.io/QRcodeLEO"
]}}) # ou CORS(app, resources={r"/*": {"origins": "https://seuusuario.github.io"}})

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Template HTML (mesmo que o seu) ---
TEMPLATE = """ ... (seu HTML aqui, sem alterações) ... """

# --- Função de geração do QR ---
def generate_qr_with_logo(url: str, logo_file=None) -> bytes:
    from PIL import ImageDraw

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url.strip())
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    qr_w, qr_h = qr_img.size
    max_logo_side = int(min(qr_w, qr_h) * 0.22)

    x = (qr_w - max_logo_side) // 2
    y = (qr_h - max_logo_side) // 2

    draw = ImageDraw.Draw(qr_img)
    draw.rectangle([(x, y), (x + max_logo_side, y + max_logo_side)], fill="white")

    if logo_file and getattr(logo_file, "filename", ""):
        if hasattr(logo_file, "mimetype") and logo_file.mimetype not in ALLOWED_MIME_TYPES:
            raise ValueError("Formato de imagem não suportado. Use PNG ou JPG.")

        logo = Image.open(logo_file).convert("RGBA")
        logo.thumbnail((max_logo_side, max_logo_side), Image.LANCZOS)

        lx, ly = logo.size
        lx_pos = x + (max_logo_side - lx) // 2
        ly_pos = y + (max_logo_side - ly) // 2

        qr_img.alpha_composite(logo, dest=(lx_pos, ly_pos))

    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

    @app.post("/api/qrcode")
def api_qrcode():
    """
    Gera QR code a partir de:
      - form-data multipart: campos 'url' e 'logo' (arquivo opcional)
      - OU JSON: {"url": "..."} (sem logo)
    Responde: {"qrb64": "<base64 PNG>"}
    """
    url_value = ""
    logo_file = None

    # aceita multipart OU JSON
    if request.content_type and "multipart/form-data" in request.content_type:
        url_value = (request.form.get("url") or "").strip()
        logo_file = request.files.get("logo")
    else:
        data = request.get_json(silent=True) or {}
        url_value = (data.get("url") or "").strip()

    if not url_value:
        return jsonify(error="Informe um link válido."), 400

    if logo_file and logo_file.filename:
        if logo_file.mimetype not in ALLOWED_MIME_TYPES:
            return jsonify(error="Formato de imagem não suportado. Use PNG ou JPG."), 400

    try:
        png_bytes = generate_qr_with_logo(url_value, logo_file)
        qrb64 = base64.b64encode(png_bytes).decode("ascii")
        return jsonify(qrb64=qrb64)
    except UnidentifiedImageError:
        return jsonify(error="Não consegui ler a imagem. Tente outro arquivo (PNG/JPG)."), 400
    except ValueError as ve:
        return jsonify(error=str(ve)), 400
    except Exception:
        logger.exception("Erro ao gerar QR via API")
        return jsonify(error="Não foi possível gerar o QR Code."), 500

# --- Handlers de erro ---
@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    flash(f"Arquivo muito grande (máx. {MAX_CONTENT_LENGTH // (1024*1024)} MB).")
    return redirect(url_for("index"))

@app.errorhandler(500)
def handle_internal_error(e):
    logger.exception("Erro interno no servidor")
    flash("Ocorreu um erro interno ao processar sua solicitação.")
    return redirect(url_for("index"))

# --- Rotas ---
@app.route("/", methods=["GET", "POST"])
def index():
    qrb64 = None
    url_value = None

    if request.method == "POST":
        url_value = (request.form.get("url") or "").strip()
        logo_file = request.files.get("logo")

        if not url_value:
            flash("Informe um link válido.")
            return redirect(url_for("index"))

        if logo_file and logo_file.filename:
            if logo_file.mimetype not in ALLOWED_MIME_TYPES:
                flash("Formato de imagem não suportado. Use PNG ou JPG.")
                return redirect(url_for("index"))

        try:
            png_bytes = generate_qr_with_logo(url_value, logo_file)
            qrb64 = base64.b64encode(png_bytes).decode("ascii")
        except UnidentifiedImageError:
            flash("Não consegui ler a imagem. Tente outro arquivo (PNG/JPG).")
            return redirect(url_for("index"))
        except ValueError as ve:
            flash(str(ve))
            return redirect(url_for("index"))
        except Exception as e:
            logger.exception("Erro ao gerar QR")
            flash("Não foi possível gerar o QR Code.")
            return redirect(url_for("index"))

    return render_template_string(TEMPLATE, qrb64=qrb64, url=url_value)

# --- Execução no Render ---
if __name__ != "__main__":
    # Quando rodar via gunicorn no Render, Flask não deve usar debug
    app.debug = False

# Execução local para desenvolvimento
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
