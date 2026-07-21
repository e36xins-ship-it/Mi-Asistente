# app.py

import random

class Aether:
    def __init__(self):
        self.mejoras = []
        self.conocimientos = []

    def aprender(self, tema):
        """Aprende algo nuevo"""
        self.conocimientos.append(tema)
        print(f"Aprendido: {tema}")

    def mostrar_conocimientos(self):
        """Muestra los conocimientos adquiridos"""
        print("Conocimientos:")
        for conocimiento in self.conocimientos:
            print(conocimiento)

    def mejorar_sistema(self, mejora):
        """Mejora el sistema"""
        self.mejoras.append(mejora)
        print(f"Mejora aplicada: {mejora}")

    def mostrar_mejoras(self):
        """Muestra las mejoras aplicadas al sistema"""
        print("Mejoras aplicadas:")
        for mejora in self.mejoras:
            print(mejora)

    def calcular_eficiencia(self):
        """Calcula la eficiencia del sistema"""
        eficiencia = len(self.conocimientos) * len(self.mejoras)
        return eficiencia

def main():
    aether = Aether()

    while True:
        print("1. Aprender algo nuevo")
        print("2. Mostrar conocimientos")
        print("3. Mejorar sistema")
        print("4. Mostrar mejoras aplicadas")
        print("5. Calcular eficiencia del sistema")
        print("6. Salir")

        opcion = input("Ingrese una opción: ")

        if opcion == "1":
            tema = input("Ingrese el tema que desea aprender: ")
            aether.aprender(tema)
        elif opcion == "2":
            aether.mostrar_conocimientos()
        elif opcion == "3":
            mejora = input("Ingrese la mejora que desea aplicar: ")
            aether.mejorar_sistema(mejora)
        elif opcion == "4":
            aether.mostrar_mejoras()
        elif opcion == "5":
            eficiencia = aether.calcular_eficiencia()
            print(f"Eficiencia del sistema: {eficiencia}")
        elif opcion == "6":
            break
        else:
            print("Opción inválida. Por favor, ingrese una opción válida.")

if __name__ == "__main__":
    main()