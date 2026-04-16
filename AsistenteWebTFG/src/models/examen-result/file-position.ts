export class FilePosition {
  file: string;
  position: number;
  constructor(position: number, file: string) {
    this.file = file;
    this.position = position;
  }
}
