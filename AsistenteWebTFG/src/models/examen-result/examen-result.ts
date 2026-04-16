import { Examen } from "../examen/examen";
import { FilePosition } from "./file-position";

export class ExamenResult {
  examen: Examen;
  files: any[];
  positions: FilePosition[];
  constructor(examen: Examen, files: any[], positions: FilePosition[]) {
    this.examen = examen;
    this.files = files;
    this.positions = positions;
  }
}
