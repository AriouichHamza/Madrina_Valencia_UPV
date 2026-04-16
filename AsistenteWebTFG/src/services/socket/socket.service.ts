import { Injectable } from '@angular/core';
import { Socket, SocketIoConfig } from 'ngx-socket-io';
import { map } from 'rxjs';
import { environment } from 'src/environments/environment';

@Injectable({
  providedIn: 'root'
})
export class SocketService {

  readonly config: SocketIoConfig = {
    url: environment.backend,
    options: {
      transports: ['websocket'],
      reconnection: true,
      autoConnect: false
    }
  }

  constructor(private socket: Socket) { }

  connect() {

    this.socket = new Socket(this.config);
    this.socket.connect();

    this.socket.on('connect', () => {
      console.log('socket:', this.socket.ioSocket.id);
    });

    this.socket.on('disconnect', (reason:any) => {
      console.log('socket disconnect:', reason);
    });
  }

  disconnect() {
    this.socket.disconnect();
  }

  isConnected() {
    return this.socket.ioSocket.connected;
  }

  insertAlumnoEmit(alumno: any) {
    this.socket.emit('insert-alumno', alumno);
  }

  insertAlumnoFromEvent() {
    return this.socket.fromEvent('insert-alumno').pipe( map( (data) => { return <any>data; } ) );
  }

  //----------------------------------------------------------------------------

  selectExamenZIP(examen: any) {
    this.socket.emit('select-examen-zip', examen);
  }

  selectExamenZIPFromEvent() {
    return this.socket.fromEvent('select-examen-zip').pipe( map( (data) => { return <any>data; } ) );
  }

  selectExamenImgs(examen:any) {
    this.socket.emit('select-examen-imgs', examen);
  }

  selectExamenImgsFromEvent() {
    return this.socket.fromEvent('select-examen-imgs').pipe( map( (data) => { return <any>data; } ) );
  }

  //----------------------------------------------------------------------------

  insertExamen(examen:any) {
    this.socket.emit('insert-examen', examen);
  }

  insertExamenProcesar() {
    return this.socket.fromEvent('insert-examen-procesar').pipe( map( (data) => { return <any>data; } ) );
  }

  insertExamenCrear() {
    return this.socket.fromEvent('insert-examen-crear').pipe( map( (data) => { return <any>data; } ) );
  }

  insertExamenGenerar() {
    return this.socket.fromEvent('insert-examen-generar').pipe( map( (data) => { return <any>data; } ) );
  }

  insertExamenPreparar() {
    return this.socket.fromEvent('insert-examen-preparar').pipe( map( (data) => { return <any>data; } ) );
  }

  insertExamenListo() {
    return this.socket.fromEvent('insert-examen-listo').pipe( map( (data) => { return <any>data; } ) );
  }

  insertExamenError() {
    return this.socket.fromEvent('insert-examen-error').pipe( map( (data) => { return <any>data; } ) );
  }
  //----------------------------------------------------------------------------
  //Nuevo Jefferson
  insertExamenPrediction(examen:any) {
    this.socket.emit('examen-predict', examen);
  }
  stopExamenPrediction(examen:any) {
    this.socket.emit('examen-predict-kill', examen);
  }

  insertExamenPredictionProcesar() {
    return this.socket.fromEvent('examen-predict-response').pipe( map( (data) => { return <any>data; } ) );
  }




}
