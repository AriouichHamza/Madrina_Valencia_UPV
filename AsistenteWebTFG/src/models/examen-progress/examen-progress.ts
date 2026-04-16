import { ExamenPaquete } from "../examen-paquete/examen-paquete";

export class ExamenProgress {

  active: boolean = true;
  buffer: ExamenPaquete[] = [];
  leer: number = 0;
  leerTotal: number = 0;
  subir: number = 0;
  subirTotal: number = 0;
  procesar: number = 0;
  procesarTotal: number = 0;
  crear: number = 0;
  crearTotal: number = 0;
  generar: number = 0;
  generarTotal: number = 0;
  preparar: number = 0;
  prepararTotal: number = 0;
  tiempo: number = 0;
}
