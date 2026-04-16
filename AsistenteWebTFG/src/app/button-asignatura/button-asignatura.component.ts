import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';

@Component({
  selector: 'app-button-asignatura',
  templateUrl: './button-asignatura.component.html',
  styleUrls: ['./button-asignatura.component.scss']
})
export class ButtonAsignaturaComponent implements OnInit {

  @Input() asignatura: any = {
    id: 0,
    acronimo: '',
    color: '',
    nombre: '',
    visible: false,
    disabled: false
  };
  @Output() deleteAsignatura = new EventEmitter();
  @Output() editAsignatura = new EventEmitter();
  @Output() filterAsignatura = new EventEmitter<boolean>();
  @Output() newExamen = new EventEmitter();

  visible: boolean = true;

  constructor() { }

  ngOnInit(): void {
  }
  
  emitDelete() { this.deleteAsignatura.emit(); }
  emitEdit() { this.editAsignatura.emit(); }
  emitFilter() { this.visible = !this.visible; this.filterAsignatura.emit(this.visible); }
  emitNew() { this.newExamen.emit(); }
}
