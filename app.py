# app.py

class Aether:
    def __init__(self):
        self.mejoras = []

    def aprender(self, nueva_funcionalidad):
        """Aprende algo nuevo y lo agrega a la lista de mejoras"""
        self.mejoras.append(nueva_funcionalidad)

    def mostrar_mejoras(self):
        """Muestra la lista de mejoras actuales"""
        print("Mejoras actuales:")
        for i, mejora in enumerate(self.mejoras):
            print(f"{i+1}. {mejora}")

    def mejorar_sistema(self):
        """Mejora el sistema en general"""
        print("Mejorando el sistema...")
        # Simula la mejora del sistema
        import time
        time.sleep(2)
        print("Sistema mejorado")

    def aprender_palabras(self):
        """Aprende un nuevo conjunto de palabras"""
        print("Aprendiendo un nuevo conjunto de palabras...")
        # Simula el aprendizaje de un nuevo conjunto de palabras
        import random
        palabras = ["hola", "mundo", "python", "aprendizaje"]
        nueva_palabra = random.choice(palabras)
        self.aprender(nueva_palabra)
        print(f"Aprendida la palabra: {nueva_palabra}")


def main():
    aether = Aether()
    while True:
        print("\nOpciones:")
        print("1. Aprender algo nuevo")
        print("2. Mostrar mejoras actuales")
        print("3. Mejorar el sistema")
        print("4. Aprender un nuevo conjunto de palabras")
        print("5. Salir")
        opcion = input("Ingrese una opción: ")
        if opcion == "1":
            nueva_funcionalidad = input("Ingrese la nueva funcionalidad: ")
            aether.aprender(nueva_funcionalidad)
        elif opcion == "2":
            aether.mostrar_mejoras()
        elif opcion == "3":
            aether.mejorar_sistema()
        elif opcion == "4":
            aether.aprender_palabras()
        elif opcion == "5":
            break
        else:
            print("Opción inválida. Por favor, ingrese una opción válida.")


if __name__ == "__main__":
    main()