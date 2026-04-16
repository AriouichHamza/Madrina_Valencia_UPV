export class Response {
  
  data: any;
  message: string;
  ok: boolean;

  constructor() {

    this.data = {};
    this.message = '';
    this.ok = false;
  }
}
