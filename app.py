class Aether:
    def __init__(self):
        self.mejoras = []
        self.conocimientos = {}

    def aprender(self, tema, descripcion):
        """Aprende algo nuevo y lo almacena en el diccionario de conocimientos."""
        self.conocimientos[tema] = descripcion
        print(f"Aether ha aprendido sobre {tema}.")

    def mejorar(self, mejora):
        """Añade una mejora al sistema."""
        self.mejoras.append(mejora)
        print(f"Aether se ha mejorado con {mejora}.")

    def mostrar_conocimientos(self):
        """Muestra todos los conocimientos adquiridos."""
        print("Conocimientos de Aether:")
        for tema, descripcion in self.conocimientos.items():
            print(f"- {tema}: {descripcion}")

    def mostrar_mejoras(self):
        """Muestra todas las mejoras realizadas."""
        print("Mejoras de Aether:")
        for mejora in self.mejoras:
            print(f"- {mejora}")


def main():
    aether = Aether()
    
    # Aprender algo nuevo
    aether.aprender("Inteligencia Artificial", "La inteligencia artificial se refiere a la creación de sistemas informáticos capaces de realizar tareas que normalmente requieren la inteligencia humana.")
    
    # Mostrar conocimientos
    aether.mostrar_conocimientos()
    
    # Realizar una mejora
    aether.mejorar("Capacidad de aprendizaje automático")
    
    # Mostrar mejoras
    aether.mostrar_mejoras()


if __name__ == "__main__":
    main()