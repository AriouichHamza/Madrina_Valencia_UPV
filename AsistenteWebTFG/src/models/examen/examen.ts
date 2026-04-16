import { ExamenProgress } from "../examen-progress/examen-progress";

export class Examen {
  id: number = 0;
  curso: string = '';
  acronimo: string = '';
  color: string = '';
  asignatura: number = 0;
  fecha: number = 0;
  nombre: string = '';
  visible: boolean = true;
  disabled: boolean = false;
  saltoPag: number = 0;
  saltoPagActivo: boolean = false;
  progress: ExamenProgress = new ExamenProgress();
}
