import json
"""
Class representing a student exam record.

Attributes:
    asignatura (str): Subject name.
    examen (str): Exam identifier.
    dni (str): Student national ID.
    nombre (str): Student first name.
    apellidos (str): Student last name.
    ini (str): Exam start time or date.
    fin (str): Exam end time or date.
    nota (str | float): Grade obtained in the exam.
"""
# Useful for representing student exam data and serializing it to JSON.

class Alumno:
    def __init__(self, asignatura, examen, dni, nombre, apellidos, ini, fin , nota):
        self.asignatura=  asignatura
        self.examen=  examen
        self.dni = dni
        self.nombre =  nombre
        self.apellidos = apellidos  
        self.ini =  ini
        self.fin =  fin
        self.nota  =  nota
    def to_json(self):
        return json.dumps(self.__dict__)