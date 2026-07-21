# app.py

class AsistenteAether:
    def __init__(self):
        self.mejoras = []
        self.objetivo_actual = "Mejorar el sistema en general"

    def aprender_nuevo_conocimiento(self):
        nuevo_conocimiento = "Aprendizaje automático"
        self.mejoras.append(nuevo_conocimiento)
        print(f"Se ha agregado el conocimiento de {nuevo_conocimiento} a la lista de mejoras")

    def mejorar_sistema(self):
        if self.objetivo_actual == "Mejorar el sistema en general":
            self.aprender_nuevo_conocimiento()
            print("El sistema se ha mejorado con éxito")
        else:
            print("El objetivo actual no es mejorar el sistema")

    def mostrar_mejoras(self):
        print("Mejoras realizadas:")
        for i, mejora in enumerate(self.mejoras):
            print(f"{i+1}. {mejora}")

def main():
    asistente = AsistenteAether()
    while True:
        print("\nOpciones:")
        print("1. Mejorar el sistema")
        print("2. Mostrar mejoras")
        print("3. Salir")
        opcion = input("Ingrese una opción: ")
        if opcion == "1":
            asistente.mejorar_sistema()
        elif opcion == "2":
            asistente.mostrar_mejoras()
        elif opcion == "3":
            break
        else:
            print("Opción inválida. Por favor, ingrese una opción válida")

if __name__ == "__main__":
    main()