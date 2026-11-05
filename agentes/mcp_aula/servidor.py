"""Servidor MCP del proyecto Aula.

Expone el contexto del repositorio como herramientas consultables por cualquier
agente. Implementa el transporte stdio de MCP con JSON-RPC 2.0 en biblioteca
estandar: sin SDK, para que el student vea el protocolo por dentro antes de
usar una abstraccion que se lo oculte.

Arranque:
    python agentes/mcp_aula/servidor.py

Registro en Claude Code: .mcp.json en la raiz del repositorio. Se lanza el fichero
por su ruta y no con "-m" porque Claude Code no garantiza que el proceso arranque
en la raiz; RAIZ se calcula desde este fichero. "python" debe ser el del .venv,
que tiene pytest (lo necesita resultado_tests).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# El paquete "aula" vive en src/ y no esta instalado: igual que tests/conftest.py,
# se anade al path para reutilizar la carga de planes del proyecto.
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from aula.reglas.planes import RUTA_PLANES, cargar_plan  # noqa: E402

PROTOCOLO = "2024-11-05"
TIEMPO_MAXIMO_TESTS = 120  # segundos
PATRON_CODIGO_PLAN = re.compile(r"^PLAN-\d{4}$")
SERVIDOR = {"name": "aula-contexto", "version": "1.0.0"}

# Codigos de error estandar de JSON-RPC 2.0.
ERROR_JSON_INVALIDO = -32700
ERROR_PETICION_INVALIDA = -32600
ERROR_METODO_DESCONOCIDO = -32601
ERROR_PARAMETROS_INVALIDOS = -32602
ERROR_INTERNO = -32603

HERRAMIENTAS = [
    {
        "name": "listar_specs",
        "description": "Devuelve el catalogo de especificaciones del proyecto con su estado y version.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "obtener_spec",
        "description": "Devuelve una spec completa con sus criterios de aceptacion, invariantes y alcance.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identificador, por ejemplo SPEC-002"}},
            "required": ["id"],
        },
    },
    {
        "name": "trazabilidad",
        "description": "Para una spec, devuelve que criterios estan cubiertos por test y cuales no.",
        "inputSchema": {
            "type": "object",
            "properties": {"spec_id": {"type": "string"}},
            "required": ["spec_id"],
        },
    },
    {
        "name": "resultado_tests",
        "description": "Ejecuta la suite y devuelve el resultado agregado y los tests fallidos.",
        "inputSchema": {
            "type": "object",
            "properties": {"ruta": {"type": "string", "description": "Subconjunto opcional de tests"}},
            "required": [],
        },
    },
    {
        "name": "version_plan",
        "description": "Devuelve la version vigente de un plan de estudios y sus parametros normativos.",
        "inputSchema": {
            "type": "object",
            "properties": {"codigo": {"type": "string"}},
            "required": ["codigo"],
        },
    },
]


# --- logica de las herramientas ----------------------------------------------

def _specs():
    return sorted((RAIZ / "specs").glob("SPEC-*.md"))


def _id_de(ruta: Path) -> str:
    return ruta.name.split("-")[0] + "-" + ruta.name.split("-")[1]


def _campo(texto: str, patron: str, defecto="desconocido") -> str:
    m = re.search(patron, texto, re.M)
    return m.group(1).strip() if m else defecto


def criterios_de(texto: str) -> list:
    """Extrae los identificadores CA-nn e INV-nn declarados en la spec."""
    return sorted(set(re.findall(r"\b(?:CA|INV)-\d{2}\b", texto)))


def listar_specs(_=None) -> dict:
    salida = []
    for ruta in _specs():
        texto = ruta.read_text(encoding="utf-8")
        salida.append({
            "id": _id_de(ruta),
            "titulo": _campo(texto, r"^#\s+SPEC-\d+:\s*(.+)$"),
            "version": _campo(texto, r"Versi[oó]n:\s*(v[\d.]+)"),
            "estado": _campo(texto, r"Estado:\s*(\w+)"),
            "criterios": len(criterios_de(texto)),
            "ruta": str(ruta.relative_to(RAIZ)),
        })
    return {"specs": salida}


def obtener_spec(args: dict) -> dict:
    ident = args["id"].upper()
    for ruta in _specs():
        if _id_de(ruta) == ident:
            texto = ruta.read_text(encoding="utf-8")
            return {"id": ident, "criterios": criterios_de(texto), "contenido": texto}
    return {"error": "spec %s no encontrada" % ident}


def _cubiertos() -> dict:
    """Mapea criterio -> lista de tests que lo declaran mediante `cubre:`."""
    mapa = {}
    for ruta in (RAIZ / "tests").rglob("test_*.py"):
        texto = ruta.read_text(encoding="utf-8")
        for bloque in re.finditer(r"def (test_\w+)\(.*?\):\s*(?:\"\"\"(.*?)\"\"\")?",
                                  texto, re.S):
            nombre, doc = bloque.group(1), bloque.group(2) or ""
            for etiqueta in re.findall(r"cubre:\s*([^\n\"]+)", doc):
                for ref in re.findall(r"(SPEC-\d+|LEG)[/-]((?:CA|INV|CAR|EQU)[-\w]*)", etiqueta):
                    clave = "%s/%s" % (ref[0], ref[1])
                    mapa.setdefault(clave, []).append("%s::%s" % (ruta.name, nombre))
    return mapa


def trazabilidad(args: dict) -> dict:
    ident = args["spec_id"].upper()
    spec = obtener_spec({"id": ident})
    if "error" in spec:
        return spec
    mapa = _cubiertos()
    cubiertos, huerfanos = {}, []
    for criterio in spec["criterios"]:
        clave = "%s/%s" % (ident, criterio)
        if clave in mapa:
            cubiertos[criterio] = mapa[clave]
        else:
            huerfanos.append(criterio)
    total = len(spec["criterios"])
    return {
        "spec": ident,
        "criterios_totales": total,
        "cubiertos": cubiertos,
        "sin_cubrir": huerfanos,
        "cobertura_pct": round(100.0 * (total - len(huerfanos)) / total, 1) if total else 0.0,
    }


def ruta_de_tests_permitida(ruta: str) -> bool:
    """True solo si la ruta queda dentro de tests/.

    La herramienta la puede llamar cualquier agente, asi que no debe servir para
    ejecutar codigo fuera de la suite.
    """
    ruta = ruta.replace("\\", "/")
    partes = ruta.split("/")
    # Exigir que empiece por "tests" ya descarta las rutas absolutas ("/etc", "C:/...")
    # y las opciones de pytest ("-p plugin"), que este tomaria como parametros.
    if partes[0] != "tests" or ".." in partes:
        return False    # ".." seria un rodeo para salir: "tests/../src"

    # Segunda barrera: la ruta real en disco (sin "::test_x") debe seguir dentro de tests/.
    fichero = ruta.split("::")[0]
    real = (RAIZ / fichero).resolve()
    carpeta_tests = (RAIZ / "tests").resolve()
    return real == carpeta_tests or carpeta_tests in real.parents


def resultado_tests(args: dict) -> dict:
    ruta = args.get("ruta") or "tests/"
    if not ruta_de_tests_permitida(ruta):
        return {"error": "ruta no permitida: %s. Solo se aceptan rutas dentro de tests/" % ruta}

    comando = [sys.executable, "-m", "pytest", ruta, "-q", "-rfE", "--no-header",
               "-p", "no:cacheprovider"]
    # La salida de pytest se captura: stdout es del protocolo y no puede llevar nada mas.
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        # stdin=DEVNULL: pytest no hereda el canal por el que llegan los mensajes MCP.
        proceso = subprocess.run(comando, cwd=RAIZ, capture_output=True, env=entorno,
                                 stdin=subprocess.DEVNULL, encoding="utf-8",
                                 errors="replace", timeout=TIEMPO_MAXIMO_TESTS)
    except subprocess.TimeoutExpired:
        return {"error": "tiempo agotado: los tests tardaron mas de %d segundos"
                         % TIEMPO_MAXIMO_TESTS}

    # pytest sale con 0 (todo pasa) o 1 (alguno falla). Otro codigo significa que no llego
    # a ejecutar los tests, por ejemplo 4 si la ruta no existe: se devuelve el motivo.
    if proceso.returncode not in (0, 1):
        motivo = (proceso.stderr.strip() or proceso.stdout.strip() or "sin salida")
        return {"error": "pytest no ejecuto los tests (codigo %d): %s"
                         % (proceso.returncode, motivo[-500:])}

    lineas = proceso.stdout.strip().splitlines()
    fallidos = []
    for linea in lineas:
        if linea.startswith("FAILED ") or linea.startswith("ERROR "):
            fallidos.append(linea)

    return {
        "ruta": ruta,
        "ok": proceso.returncode == 0,
        "codigo_salida": proceso.returncode,
        "resumen": lineas[-1] if lineas else "sin salida",
        "fallidos": fallidos,
    }


def version_plan(args: dict) -> dict:
    codigo = args["codigo"].strip().upper()
    # El codigo acaba siendo un nombre de fichero: sin esta comprobacion,
    # "../specs/SPEC-001" intentaria abrir un fichero fuera de datos/planes.
    if not PATRON_CODIGO_PLAN.match(codigo):
        return {"error": "codigo de plan no valido: %s. Formato esperado: PLAN-AAAA"
                         % args["codigo"]}
    if not (RUTA_PLANES / ("%s.json" % codigo)).is_file():
        return {"error": "plan %s no encontrado" % codigo}

    plan = cargar_plan(codigo)
    return {
        "codigo": plan.codigo,
        "version": plan.version,
        "creditos_titulo": plan.creditos_titulo,
        "limite_creditos_curso": plan.limite_creditos_curso,
        "max_convocatorias": plan.max_convocatorias,
        "umbral_final_carrera": plan.umbral_final_carrera,
        "asignaturas": len(plan.asignaturas),
    }


IMPLEMENTACION = {
    "listar_specs": listar_specs,
    "obtener_spec": obtener_spec,
    "trazabilidad": trazabilidad,
    "resultado_tests": resultado_tests,
    "version_plan": version_plan,
}


# --- transporte JSON-RPC sobre stdio ------------------------------------------

def manejar(mensaje: dict):
    """Responde a un mensaje JSON-RPC 2.0. Devuelve None si es una notificacion.

    Una notificacion es un mensaje sin "id": el cliente avisa de algo y no espera
    respuesta (por ejemplo "notifications/initialized" despues del saludo).
    """
    if "id" not in mensaje:
        return None
    if "method" not in mensaje:
        return None     # es una respuesta del cliente: JSON-RPC prohibe contestarla

    ident = mensaje["id"]
    metodo = mensaje["method"]
    parametros = mensaje.get("params") or {}

    if mensaje.get("jsonrpc") != "2.0" or not isinstance(metodo, str):
        return _error(ident, ERROR_PETICION_INVALIDA, "se esperaba jsonrpc 2.0 y un method de texto")

    if metodo == "initialize":
        return _ok(ident, {
            "protocolVersion": PROTOCOLO,
            "capabilities": {"tools": {}},
            "serverInfo": SERVIDOR,
        })
    if metodo == "ping":
        return _ok(ident, {})
    if metodo == "tools/list":
        return _ok(ident, {"tools": HERRAMIENTAS})
    if metodo == "tools/call":
        return _llamar_herramienta(ident, parametros)
    return _error(ident, ERROR_METODO_DESCONOCIDO, "metodo no soportado: %s" % metodo)


def _llamar_herramienta(ident, parametros) -> dict:
    # Errores del cliente (pide algo que no existe o mal formado): error de protocolo.
    # Se comprueban los tipos antes de usarlos: un "arguments": 5 no debe tumbar el servidor.
    if not isinstance(parametros, dict):
        return _error(ident, ERROR_PARAMETROS_INVALIDOS, "params debe ser un objeto")
    nombre = parametros.get("name")
    argumentos = parametros.get("arguments")
    if argumentos is None:
        argumentos = {}     # una herramienta sin argumentos puede llegar sin "arguments"
    if not isinstance(nombre, str) or not isinstance(argumentos, dict):
        return _error(ident, ERROR_PARAMETROS_INVALIDOS,
                      "name debe ser texto y arguments un objeto")

    if nombre not in IMPLEMENTACION:
        return _error(ident, ERROR_PARAMETROS_INVALIDOS, "herramienta desconocida: %s" % nombre)
    faltan = _argumentos_que_faltan(nombre, argumentos)
    if faltan:
        return _error(ident, ERROR_PARAMETROS_INVALIDOS,
                      "faltan argumentos para %s: %s" % (nombre, ", ".join(faltan)))

    # Errores de la herramienta: se devuelven como resultado con isError, para que
    # el modelo los lea y pueda corregirse en lugar de perder la conexion.
    try:
        resultado = IMPLEMENTACION[nombre](argumentos)
    except Exception as fallo:
        error = {"error": "%s: %s" % (type(fallo).__name__, fallo)}
        return _ok(ident, _contenido(error, es_error=True))
    return _ok(ident, _contenido(resultado, es_error="error" in resultado))


def _argumentos_que_faltan(nombre: str, argumentos: dict) -> list:
    """Compara los argumentos recibidos con los "required" del inputSchema de la herramienta."""
    obligatorios = []
    for herramienta in HERRAMIENTAS:
        if herramienta["name"] == nombre:
            obligatorios = herramienta["inputSchema"]["required"]

    faltan = []
    for argumento in obligatorios:
        if argumento not in argumentos:
            faltan.append(argumento)
    return faltan


def _contenido(datos: dict, es_error: bool) -> dict:
    """Envuelve el resultado como lo espera MCP: una lista de bloques de texto."""
    texto = json.dumps(datos, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": texto}], "isError": es_error}


def _ok(ident, resultado):
    return {"jsonrpc": "2.0", "id": ident, "result": resultado}


def _error(ident, codigo, mensaje):
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": codigo, "message": mensaje}}


def responder_linea(linea: str):
    """Convierte una linea de texto en respuesta. Devuelve None si no hay que contestar."""
    try:
        mensaje = json.loads(linea)
    except json.JSONDecodeError:
        return _error(None, ERROR_JSON_INVALIDO, "la linea no es JSON valido")
    if not isinstance(mensaje, dict):
        return _error(None, ERROR_PETICION_INVALIDA, "se esperaba un objeto JSON-RPC")
    return manejar(mensaje)


def principal():
    """Transporte stdio: un mensaje JSON por linea en stdin, una respuesta por linea en stdout.

    stdout es exclusivo del protocolo: cualquier otro print romperia la conversacion
    con el cliente. La respuesta sale en ASCII (tildes escapadas como \\u00f3) para
    no depender de la codificacion de la consola, que en Windows no es UTF-8.
    """
    # errors="replace": un byte invalido se convierte en el caracter de reemplazo (U+FFFD)
    # en vez de cortar el bucle.
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            respuesta = responder_linea(linea)
        except Exception as fallo:
            # Red de seguridad: un fallo inesperado no debe matar el proceso,
            # porque el cliente perderia el servidor para el resto de la sesion.
            respuesta = _error(None, ERROR_INTERNO, "error interno: %s" % fallo)
        if respuesta is not None:
            sys.stdout.write(json.dumps(respuesta) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    principal()
