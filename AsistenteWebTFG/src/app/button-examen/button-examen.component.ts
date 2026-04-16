import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';

@Component({
  selector: 'app-button-examen',
  templateUrl: './button-examen.component.html',
  styleUrls: ['./button-examen.component.scss']
})
export class ButtonExamenComponent implements OnInit {

  readonly infoLeer: string = 'Leer los documentos cargados';
  readonly infoSubir: string = 'Subir los documentos';
  readonly infoProcesar: string = 'Documetos subidos';
  readonly infoCrear: string = 'Documentos creados';
  readonly infoGenerar: string = 'Generar un único documentos';
  readonly infoPreparar: string = 'Preparar el documento para las calificaciones';

  @Input() examen: any = {
    id: 0,
    acronimo: '',
    color: '',
    nombre: '',
    fecha: 0,
    visible: false,
    disabled: false
  };
  @Output() openExamen = new EventEmitter();
  @Output() openExamenAvanzado = new EventEmitter();
  constructor() { }

  ngOnInit(): void {
  }

  dateToString(date:number) {
    let d = new Date(date);

    let day = d.getDate();
    let month = d.getMonth() + 1;
    let year = d.getFullYear();

    return `${day < 10 ? '0' + day : day}/${month < 10 ? '0' + month : month}/${year}`;
  }

  emitOpen() { this.openExamen.emit(); }
  
  emitOpenAvanzado() { this.openExamenAvanzado.emit(); }
  
  openGeneric(){
    if(this.examen.isAvanzado == 1) this.emitOpenAvanzado();
    else this.emitOpen();
  }
  getPerc(cant: number, total: number) {
    if (cant == 0 && total == 0) return '0%';
    return Math.round((cant / total) * 100) + '%';
  }
}
