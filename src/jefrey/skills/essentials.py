"""Skill: essenciais locais (hora, calculo, clima, arquivos numa pasta isolada)."""
from __future__ import annotations

import ast
import logging
import math
import operator
import os
import re
from datetime import datetime
from pathlib import Path

import httpx

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool

logger = logging.getLogger(__name__)

WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro"]

# ------------------------------------------------------------------ calculadora segura
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"sqrt": math.sqrt, "abs": abs, "round": round, "min": min, "max": max,
          "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log, "log10": math.log10}
_CONSTS = {"pi": math.pi, "e": math.e}
MAX_EXPR = 200
MAX_POW = 1000


class CalcError(ValueError):
    pass


def safe_eval(expression: str) -> float | int:
    """Avalia aritmetica sem eval(): so numeros, operadores e funcoes matematicas conhecidas."""
    # virgula decimal brasileira so entre digitos ("1,5"); em "round(2.5, 1)" a virgula separa argumentos
    expr = re.sub(r"(?<=\d),(?=\d)", ".", (expression or "").strip()).replace("×", "*").replace("÷", "/").replace("^", "**")
    if not expr:
        raise CalcError("expressao vazia")
    if len(expr) > MAX_EXPR:
        raise CalcError("expressao longa demais")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise CalcError("expressao invalida")

    def ev(n: ast.AST):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > MAX_POW:
                raise CalcError("expoente grande demais")
            if isinstance(n.op, (ast.Div, ast.FloorDiv, ast.Mod)) and b == 0:
                raise CalcError("divisao por zero")
            return _BIN[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UN:
            return _UN[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Name) and n.id in _CONSTS:
            return _CONSTS[n.id]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
            return _FUNCS[n.func.id](*[ev(a) for a in n.args])
        raise CalcError("so aceito numeros e operacoes matematicas")

    try:
        result = ev(tree)
    except CalcError:
        raise
    except (OverflowError, ValueError, TypeError, ZeroDivisionError) as e:
        raise CalcError(f"nao consegui calcular ({type(e).__name__})")
    if isinstance(result, float):
        if math.isnan(result) or math.isinf(result):
            raise CalcError("resultado invalido")
        if result == int(result) and abs(result) < 1e15:
            return int(result)
        return round(result, 10)
    return result


# ------------------------------------------------------------------ arquivos isolados
MAX_READ = 100_000
MAX_WRITE = 200_000
_SAFE_USER = re.compile(r"[^A-Za-z0-9_.@-]")


def files_root() -> Path:
    return Path(os.getenv("JEFREY_FILES_DIR", "data/files")).resolve()


def user_dir(user_id: str | None) -> Path:
    uid = _SAFE_USER.sub("_", (user_id or "anonymous"))[:64] or "anonymous"
    d = files_root() / uid
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_path(user_id: str | None, relative: str) -> Path:
    """Resolve um caminho DENTRO da pasta do usuario. Qualquer tentativa de sair dela e recusada."""
    base = user_dir(user_id).resolve()
    rel = (relative or "").strip().replace("\\", "/").lstrip("/")
    if not rel or "\x00" in rel:
        raise PermissionError("caminho invalido")
    target = (base / rel).resolve()
    if target != base and base not in target.parents:
        raise PermissionError("o caminho sai da sua pasta")
    return target


class EssentialsSkill(SkillBase):
    metadata = SkillMetadata(
        name="essentials",
        description="Hora e data, calculadora, clima e arquivos numa pasta só sua",
        tags=["utility", "local"],
        enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.current_time, self.calculator, self.weather, self.files_list, self.files_read, self.files_write]

    @tool(description="Informa a data e a hora atuais (fuso de Brasilia por padrao)")
    async def current_time(self, timezone: str = "America/Sao_Paulo", user_id: str | None = None) -> str:
        try:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(timezone))
        except Exception:
            now = datetime.now().astimezone()
        return (f"{WEEKDAYS[now.weekday()]}, {now.day} de {MONTHS[now.month - 1]} de {now.year}, "
                f"{now:%H:%M} (fuso {now.tzname() or timezone})")

    @tool(description="Calcula uma expressao matematica (+ - * / ** parenteses, sqrt, round, pi)")
    async def calculator(self, expression: str, user_id: str | None = None) -> str:
        try:
            return f"{expression.strip()} = {safe_eval(expression)}"
        except CalcError as e:
            return f"Nao consegui calcular: {e}."

    @tool(description="Mostra o clima atual de uma cidade")
    async def weather(self, city: str, user_id: str | None = None) -> str:
        city = (city or "").strip()
        if not city or len(city) > 80:
            return "Informe o nome de uma cidade."
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                g = await c.get("https://geocoding-api.open-meteo.com/v1/search",
                                params={"name": city, "count": 1, "language": "pt"})
                g.raise_for_status()
                results = g.json().get("results") or []
                if not results:
                    return f"Nao encontrei a cidade '{city}'."
                r = results[0]
                w = await c.get("https://api.open-meteo.com/v1/forecast", params={
                    "latitude": r["latitude"], "longitude": r["longitude"],
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,precipitation",
                    "timezone": "auto"})
                w.raise_for_status()
                cur = w.json().get("current") or {}
        except Exception as e:
            logger.warning("weather falhou: %s", type(e).__name__)
            return "Nao consegui consultar o clima agora (sem internet ou servico fora do ar)."
        place = ", ".join(x for x in (r.get("name"), r.get("admin1")) if x)

        def n(v) -> str:  # 17.3 -> "17,3"
            return str(v).replace(".", ",")

        rain = cur.get("precipitation") or 0
        return (f"Agora em {place}: {n(cur.get('temperature_2m'))} °C (sensação de {n(cur.get('apparent_temperature'))} °C), "
                f"umidade de {n(cur.get('relative_humidity_2m'))}%, vento de {n(cur.get('wind_speed_10m'))} km/h, "
                + (f"com chuva de {n(rain)} mm." if rain else "sem chuva agora."))

    @tool(description="Lista os arquivos da sua pasta local do Jefrey")
    async def files_list(self, folder: str = ".", user_id: str | None = None) -> str:
        try:
            base = user_dir(user_id)
            target = base if folder in ("", ".", "/") else safe_path(user_id, folder)
            if not target.is_dir():
                return "Essa pasta nao existe."
            items = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:200]
            if not items:
                return "A pasta esta vazia."
            return "\n".join(f"{'[pasta] ' if p.is_dir() else ''}{p.name}" + ("" if p.is_dir() else f" ({p.stat().st_size} bytes)")
                             for p in items)
        except PermissionError as e:
            return f"Nao permitido: {e}."

    @tool(description="Le um arquivo de texto da sua pasta local do Jefrey")
    async def files_read(self, path: str, user_id: str | None = None) -> str:
        try:
            p = safe_path(user_id, path)
            if not p.is_file():
                return "Esse arquivo nao existe."
            data = p.read_bytes()[:MAX_READ + 1]
            text = data.decode("utf-8", errors="replace")
            return text[:MAX_READ] + ("\n...[arquivo cortado]" if len(data) > MAX_READ else "")
        except PermissionError as e:
            return f"Nao permitido: {e}."

    @tool(description="Grava um arquivo de texto na sua pasta local do Jefrey")
    async def files_write(self, path: str, content: str, user_id: str | None = None) -> str:
        try:
            if len(content.encode("utf-8")) > MAX_WRITE:
                return "Conteudo grande demais (maximo 200 KB)."
            p = safe_path(user_id, path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Arquivo '{path}' gravado ({len(content)} caracteres)."
        except PermissionError as e:
            return f"Nao permitido: {e}."


# Auto-registro
@skill("essentials", "Hora e data, calculadora, clima e arquivos numa pasta só sua", tags=["utility", "local"])
class _EssentialsSkillWrapper(EssentialsSkill):
    pass
