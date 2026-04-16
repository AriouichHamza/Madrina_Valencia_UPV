export class ExamenPaquete {
  id: string;
  op: string;
  payload: string;

  constructor(id: string, op: string, payload: string) {
    this.id = id;
    this.op = op;
    this.payload = payload;
  }
}
