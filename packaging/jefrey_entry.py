"""Ponto de entrada do programa empacotado (Jefrey.exe)."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from src.jefrey.native.launcher import main

    raise SystemExit(main(sys.argv[1:]))
