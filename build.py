#!/usr/bin/env python3
import argparse, os, sys, shutil, subprocess
from pathlib import Path
from datetime import datetime, UTC

def run(cmd, check=True):
    print(">>", " ".join(cmd), flush=True)
    try:
        return subprocess.run(cmd, check=check)
    except subprocess.CalledProcessError as e:
        print("\n[ERRO] Comando falhou:", e, flush=True)
        sys.exit(e.returncode)

def ensure_ico(png_path: Path, ico_path: Path):
    print(f"[info] Gerando ICO de {png_path} -> {ico_path}", flush=True)
    from PIL import Image
    if not png_path.exists():
        sys.exit(f"ERRO: PNG não encontrado em {png_path}")
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(png_path).convert("RGBA")
    sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
    img.save(ico_path, format="ICO", sizes=sizes)
    print(f"[ok] ICO gerado em {ico_path}", flush=True)

def write_version_file(path: Path, company: str, product: str, version: str, exe_name: str):
    print(f"[info] Escrevendo version-file em {path}", flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"""
# Auto-gerado em {datetime.now(UTC).isoformat()}
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version.replace('.', ',')}, 0),
    prodvers=({version.replace('.', ',')}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x4,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', '{company}'),
        StringStruct('FileDescription', '{product}'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', '{exe_name}'),
        StringStruct('OriginalFilename', '{exe_name}.exe'),
        StringStruct('ProductName', '{product}'),
        StringStruct('ProductVersion', '{version}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""".strip()
    path.write_text(content, encoding="utf-8")
    print(f"[ok] version-file escrito em {path}", flush=True)

def main():
    print(f"[info] Python: {sys.executable}", flush=True)
    print(f"[info] CWD: {os.getcwd()}", flush=True)

    parser = argparse.ArgumentParser(description="Build Gerador de QRCode")
    parser.add_argument("--mode", choices=["onedir","onefile"], default="onedir")
    parser.add_argument("--name", default="GeradorQRCodeLEO")
    parser.add_argument("--company", default="LEO Clube Seara Centenário")
    parser.add_argument("--product", default="Gerador de QR Code LEO")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--icon-png", default="static/logo_leo.png")
    parser.add_argument("--icon-ico", default="static/logo_leo.ico")
    parser.add_argument("--extra-pyinstaller-args", default="")
    args = parser.parse_args()

    # Passo 1: ICO
    ensure_ico(Path(args.icon_png), Path(args.icon_ico))

    # Passo 2: version file
    build_dir = Path("build_meta")
    version_file = build_dir / "version_info.txt"
    write_version_file(version_file, args.company, args.product, args.version, args.name)

    # Passo 3: comando PyInstaller
    add_data_sep = ";" if os.name == "nt" else ":"
    add_data_arg = f"static{add_data_sep}static"
    cmd = [sys.executable, "-m", "PyInstaller"]
    cmd += ["--onefile" if args.mode=="onefile" else "--onedir"]
    cmd += [
        "--noconsole",
        f"--name={args.name}",
        f"--icon={args.icon_ico}",
        f"--version-file={str(version_file)}",
        f"--add-data={add_data_arg}",
    ]
    if args.extra_pyinstaller_args.strip():
        cmd += args.extra_pyinstaller_args.strip().split()
    cmd += ["app.py"]

    run(cmd)

    # Passo 4: onde ficou o exe
    exe = (Path("dist") / (args.name + ".exe")) if args.mode=="onefile" else (Path("dist")/args.name/(args.name+".exe"))
    print(f"[ok] Build finalizado. Executável esperado em: {exe}", flush=True)
    if not exe.exists():
        print("[alerta] Executável não encontrado. Verifique logs acima.", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("[FATAL]", repr(e))
        raise
