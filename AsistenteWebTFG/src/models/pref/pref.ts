export class Pref {

  encode: string;
  sep: string;
  cabecera: boolean;

  constructor() {
    this.encode = 'utf8';
    this.sep = ';'
    this.cabecera = false;
  }
}
