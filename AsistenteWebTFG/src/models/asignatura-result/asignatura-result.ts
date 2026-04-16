import { Alumno } from "../alumno/alumno";
import { Asignatura } from "../asignatura/asignatura";

export class AsignaturaResult {
  asignatura: Asignatura;
  alumnos: Alumno[] | undefined;
  constructor(asignatura: Asignatura, alumnos: Alumno[] | undefined) {
    this.asignatura = asignatura;
    this.alumnos = alumnos;
  }
}
