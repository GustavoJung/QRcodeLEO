import base64
from io import BytesIO

from PIL import Image, UnidentifiedImageError, ImageFile
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from flask import Flask, request, redirect, url_for, render_template_string, flash
from werkzeug.exceptions import RequestEntityTooLarge

Image.MAX_IMAGE_PIXELS = 25_000_000
ImageFile.LOAD_TRUNCATED_IMAGES = True

app = Flask(__name__, static_folder="static")
app.secret_key = "change-me"

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

TEMPLATE = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Gerador de QR Code</title>
  <link rel="icon" type="image/png" href="{{ url_for('static', filename='logo_leo.png') }}">
  <script src="https://cdn.tailwindcss.com"></script>
  <meta name="color-scheme" content="light dark">
</head>
<body class="min-h-screen bg-gray-50 text-gray-900 dark:bg-neutral-900 dark:text-neutral-100">
  <header class="py-6 flex flex-col items-center justify-center">
    <img src="{{ url_for('static', filename='logo_leo.png') }}" alt="Logo" class="w-20 h-20 mb-3 rounded-full shadow">
    <h1 class="text-center text-3xl font-semibold">Gerador de QR Code</h1>
    <p class="mt-2 text-center text-sm text-gray-500 dark:text-neutral-400">
      Insira o link e, se quiser, um logo opcional para o centro do QR.
    </p>
  </header>

  <main class="max-w-3xl mx-auto px-4 pb-16">
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <div class="mb-6 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-amber-800 dark:border-amber-600 dark:bg-amber-950/40 dark:text-amber-200">
          {{ messages[0] }}
        </div>
      {% endif %}
    {% endwith %}

    <div class="grid gap-6 md:grid-cols-2">
      <form id="qr-form" method="POST" enctype="multipart/form-data"
            class="rounded-2xl bg-white/70 dark:bg-neutral-800/70 backdrop-blur border border-gray-200 dark:border-neutral-700 p-6 shadow-sm">
        <label class="block text-sm font-medium mb-2" for="url">Link do QR Code</label>
        <input required type="url" id="url" name="url"
               placeholder="https://exemplo.com/meu-link"
               value="{{ url or '' }}"
               class="w-full rounded-xl border border-gray-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"/>

        <div class="mt-5">
          <label class="block text-sm font-medium mb-2" for="logo">
            Logo (opcional) — PNG/JPG, ideal quadrado
          </label>
          <input type="file" id="logo" name="logo" accept="image/png, image/jpeg, image/jpg"
                 class="w-full text-sm file:mr-4 file:rounded-xl file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-white hover:file:bg-indigo-700"/>
          <p class="mt-2 text-xs text-gray-500 dark:text-neutral-400">
            Tamanho máx. do arquivo: <strong>10 MB</strong>.
          </p>
        </div>

        <div class="mt-6 flex items-center gap-3">
          <button type="submit"
                  class="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-4 py-2 text-white text-sm font-medium hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500">
            Gerar QR Code
          </button>
          <button type="submit" formmethod="get" formaction="/" formnovalidate
                  class="rounded-xl border border-gray-300 dark:border-neutral-700 px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-neutral-800">
            Limpar
          </button>
        </div>
      </form>

      <div class="rounded-2xl bg-white/70 dark:bg-neutral-800/70 backdrop-blur border border-gray-200 dark:border-neutral-700 p-6 shadow-sm">
        <h2 class="text-lg font-semibold">Preview</h2>
        {% if qrb64 %}
          <img src="data:image/png;base64,{{ qrb64 }}" alt="QR Code" class="mt-4 mx-auto w-full max-w-xs rounded-xl border border-gray-200 dark:border-neutral-700"/>
          <a download="qrcode.png" href="data:image/png;base64,{{ qrb64 }}"
             class="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-emerald-600 px-4 py-2 text-white text-sm font-medium hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500">
             Baixar PNG
          </a>
        {% else %}
          <div class="mt-6 grid place-items-center h-56 rounded-xl border border-dashed border-gray-300 dark:border-neutral-700 text-sm text-gray-500 dark:text-neutral-400">
            O QR aparecerá aqui após gerar.
          </div>
        {% endif %}
      </div>
    </div>

    <footer class="mt-12 text-center text-xs text-gray-400">
        LEO Clube Seara Centenário - Distrito LEO LD-8
    </footer>
  </main>

  <script>
    // Limite de 10 MB no client
    const form = document.getElementById('qr-form');
    const logoInput = document.getElementById('logo');
    form.addEventListener('submit', (e) => {
      const f = logoInput.files && logoInput.files[0];
      if (f && f.size > 10 * 1024 * 1024) {
        e.preventDefault();
        alert('Arquivo do logo excede 10 MB.');
      }
    });
  </script>
</body>
</html>
"""

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

    # Tamanho fixo da janela central (mesma proporção de antes)
    qr_w, qr_h = qr_img.size
    max_logo_side = int(min(qr_w, qr_h) * 0.22)

    # Calcula posição central
    x = (qr_w - max_logo_side) // 2
    y = (qr_h - max_logo_side) // 2

    # Fundo branco fixo (mesmo se não houver logo)
    draw = ImageDraw.Draw(qr_img)
    draw.rectangle([(x, y), (x + max_logo_side, y + max_logo_side)], fill="white")

    # Se tiver logo, ajusta e cola
    if logo_file and getattr(logo_file, "filename", ""):
        if hasattr(logo_file, "mimetype") and logo_file.mimetype not in ("image/png", "image/jpeg", "image/jpg"):
            raise ValueError("Formato de imagem não suportado. Use PNG ou JPG.")

        logo = Image.open(logo_file).convert("RGBA")
        logo.thumbnail((max_logo_side, max_logo_side), Image.LANCZOS)

        lx, ly = logo.size
        # centraliza o logo na janela
        lx_pos = x + (max_logo_side - lx) // 2
        ly_pos = y + (max_logo_side - ly) // 2

        qr_img.alpha_composite(logo, dest=(lx_pos, ly_pos))

    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    flash("Arquivo muito grande (máx. 10 MB).")
    return redirect(url_for("index"))

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
            if logo_file.mimetype not in ("image/png", "image/jpeg", "image/jpg"):
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
            print("Erro ao gerar QR:", repr(e))
            flash("Não foi possível gerar o QR Code.")
            return redirect(url_for("index"))

    return render_template_string(TEMPLATE, qrb64=qrb64, url=url_value)

if __name__ == "__main__":
    import webbrowser, threading
    port = 5000

    def open_browser():
        webbrowser.open(f"http://127.0.0.1:{port}")

    threading.Timer(0.8, open_browser).start()
    app.run(host="127.0.0.1", port=port)
