import { Asignatura } from "../asignatura/asignatura";
import { Examen } from "../examen/examen";

export class CursoInfo {
  curso: string = '';
  asignaturas: Asignatura[] = [];
  examenes: Examen[] = [];
  visible: boolean = true;

  constructor(curso: string, asignaturas: Asignatura[], examenes: Examen[]) {
    this.curso = curso;
    this.asignaturas = asignaturas;
    this.examenes = examenes;
    this.visible = true;
  }
}
