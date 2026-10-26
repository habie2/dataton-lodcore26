"""Ejecuta las cuatro etapas en orden y genera carga/*.csv.

Uso:   python pipeline/ejecutar_todo.py
Antes: pip install -r pipeline/requirements.txt  y los ficheros originales en fuentes/
"""
import os, runpy, sys

aqui = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, aqui)
for etapa in ("p1_municipios", "p2_suelo_alquiler", "p3_servicios", "p4_comercio"):
    print(f"\n== {etapa}")
    runpy.run_path(os.path.join(aqui, f"{etapa}.py"), run_name="__main__")
print("\nListo: CSV en carga/")
