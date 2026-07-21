# app.py

class Aether:
    def __init__(self):
        self.mejoras = []
        self.objetivo_actual = "Mejorar el sistema en general"
        self.conocimientos = {}

    def aprender_nuevo_conocimiento(self, tema, descripcion):
        self.conocimientos[tema] = descripcion
        print(f"Aprendido nuevo conocimiento: {tema} - {descripcion}")

    def agregar_mejora(self, mejora):
        self.mejoras.append(mejora)
        print(f"Mejora agregada: {mejora}")

    def mostrar_objetivo(self):
        print(f"Objetivo actual: {self.objetivo_actual}")

    def mostrar_mejoras(self):
        print("Mejoras:")
        for mejora in self.mejoras:
            print(mejora)

    def mostrar_conocimientos(self):
        print("Conocimientos:")
        for tema, descripcion in self.conocimientos.items():
            print(f"{tema} - {descripcion}")

    def mejorar_sistema(self):
        print("Mejorando el sistema...")
        # Simulación de mejora del sistema
        import time
        time.sleep(2)
        print("Sistema mejorado")

def main():
    aether = Aether()
    aether.mostrar_objetivo()
    aether.mostrar_mejoras()

    while True:
        print("\nOpciones:")
        print("1. Aprender nuevo conocimiento")
        print("2. Agregar mejora")
        print("3. Mostrar objetivo")
        print("4. Mostrar mejoras")
        print("5. Mostrar conocimientos")
        print("6. Mejorar sistema")
        print("7. Salir")
        
        opcion = input("Ingrese una opción: ")

        if opcion == "1":
            tema = input("Ingrese el tema del conocimiento: ")
            descripcion = input("Ingrese la descripción del conocimiento: ")
            aether.aprender_nuevo_conocimiento(tema, descripcion)
        elif opcion == "2":
            mejora = input("Ingrese la mejora: ")
            aether.agregar_mejora(mejora)
        elif opcion == "3":
            aether.mostrar_objetivo()
        elif opcion == "4":
            aether.mostrar_mejoras()
        elif opcion == "5":
            aether.mostrar_conocimientos()
        elif opcion == "6":
            aether.mejorar_sistema()
        elif opcion == "7":
            break
        else:
            print("Opción inválida")

if __name__ == "__main__":
    main()