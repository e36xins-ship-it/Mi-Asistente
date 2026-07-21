# app.py

class Aether:
    def __init__(self):
        self.mejoras = []

    def aprender_nuevo(self, nuevo_conocimiento):
        """Aprende algo nuevo y lo agrega a la lista de mejoras"""
        self.mejoras.append(nuevo_conocimiento)

    def mostrar_mejoras(self):
        """Muestra la lista de mejoras"""
        print("Mejoras realizadas:")
        for mejora in self.mejoras:
            print(mejora)

    def mejorar_sistema(self):
        """Mejora el sistema en general"""
        print("Mejorando el sistema...")
        # Lógica para mejorar el sistema
        nuevo_conocimiento = "Conocimiento adquirido sobre Machine Learning"
        self.aprender_nuevo(nuevo_conocimiento)
        print("Sistema mejorado con éxito")

def main():
    aether = Aether()
    while True:
        print("\nOpciones:")
        print("1. Mejorar sistema")
        print("2. Mostrar mejoras")
        print("3. Aprender algo nuevo")
        print("4. Salir")
        opcion = input("Ingrese una opción: ")
        
        if opcion == "1":
            aether.mejorar_sistema()
        elif opcion == "2":
            aether.mostrar_mejoras()
        elif opcion == "3":
            nuevo_conocimiento = input("Ingrese algo nuevo que aprender: ")
            aether.aprender_nuevo(nuevo_conocimiento)
        elif opcion == "4":
            break
        else:
            print("Opción inválida")

if __name__ == "__main__":
    main()